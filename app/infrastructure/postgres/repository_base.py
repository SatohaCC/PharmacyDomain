"""集約とテーブルの対応、Repository 共通処理、制約違反判定。

集約は payload（JSONB）を正とし、検索・一意性制約に要る値だけを列へ複製する。
この設計では同じ導出が「書き込み」と「復元時の照合」の2箇所に現れるため、
:class:`AggregateMapping` に1度だけ書いて両方が同じ関数を使うようにする。
:class:`PostgresRepositoryBase` はその対応を受け取って読み書きを行う。
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, cast

from sqlalchemy import CursorResult, Select, Table, func
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.foundation.exceptions import ConcurrentModificationError
from app.infrastructure.postgres.codec import (
    PersistenceMappingError,
    decode_aggregate,
    encode_aggregate,
)
from app.infrastructure.postgres.connection import PostgresUnitOfWork

# --------------------------------------------------------------------------
# 制約違反の判定
# --------------------------------------------------------------------------

# 例外連鎖のうち、SQLAlchemy と DBAPI ラッパが明示的に張るリンクだけを辿る。
# ``__context__`` は「処理中に別の例外が起きた」だけの無関係な例外も繋ぐため、
# 別の制約名を拾ってしまう危険がある。
_LINK_ATTRIBUTES = ("orig", "__cause__")


def constraint_name(error: IntegrityError) -> str | None:
    """違反した制約の名前を取り出す。

    asyncpg の例外は SQLAlchemy が DBAPI 互換のラッパへ翻訳して ``orig`` に入れる。
    そのラッパは ``sqlstate`` しか持たず、サーバが返した制約名は翻訳前の元例外
    （``__cause__``）の ``constraint_name`` にだけ残る。psycopg2 の ``diag`` は
    asyncpg には存在しないので、例外連鎖をたどって探す。
    """
    for candidate in _linked_errors(error):
        name = getattr(candidate, "constraint_name", None)
        if isinstance(name, str) and name:
            return name
    return None


def _linked_errors(error: BaseException) -> Iterator[BaseException]:
    """例外連鎖を、同じ例外を二度たどらずに列挙する。"""
    seen: set[int] = set()
    pending: list[BaseException] = [error]
    while pending:
        current = pending.pop(0)
        if id(current) in seen:
            continue
        seen.add(id(current))
        yield current
        for attribute in _LINK_ATTRIBUTES:
            linked = getattr(current, attribute, None)
            if isinstance(linked, BaseException):
                pending.append(linked)


# --------------------------------------------------------------------------
# 集約とテーブルの対応
# --------------------------------------------------------------------------


def closed_date_range_matches(
    actual: object,
    expected: Range[date] | None,
) -> bool:
    """DB の日付範囲がドメインの閉区間と同じ期間を表すか確認する。

    PostgreSQL は ``daterange`` の離散値を ``[開始, 終了翌日)`` へ正規化する
    一方、テスト用行や別ドライバは閉区間 ``[開始, 終了]`` を返すことがある。
    境界表現ではなく閉区間として比較し、payload と検索列の意味的な一致を
    検証する。
    """
    if expected is None:
        return actual is None
    if not isinstance(actual, Range):
        return False
    actual_range = actual
    if actual_range.lower != expected.lower or not actual_range.lower_inc:
        return False
    return _closed_upper(actual_range) == _closed_upper(expected)


def _closed_upper(value: Range[date]) -> date | None:
    """範囲の上端を、閉区間の終了日へ揃える。"""
    upper = value.upper
    if upper is None:
        return None
    return upper if value.upper_inc else upper - timedelta(days=1)


def _column_matches(actual: object, expected: object) -> bool:
    """列の値が、集約から導いた値と同じものを表すか判定する。

    ``daterange`` だけは ``==`` で判定できない。PostgreSQL が境界表現を正規化
    するため、同じ期間でも ``Range`` の値としては等しくならない。
    """
    if isinstance(expected, Range):
        return closed_date_range_matches(actual, cast("Range[date]", expected))
    if isinstance(actual, Range):
        return False
    return actual == expected


@dataclass(frozen=True, slots=True)
class AggregateMapping[AggregateT]:
    """1つの集約と、それを保存するテーブルの対応。

    ``search_columns`` は payload を**含まない**。payload は :meth:`row_values`
    が付けるので、検索列の一覧としてそのまま照合に使える。書き込みと照合が同じ
    関数を使うので、片方だけ直して「保存はできるが読み戻せない行」を作れない。
    """

    table: Table
    aggregate_type: type[AggregateT]
    label: str
    search_columns: Callable[[AggregateT], dict[str, object]]

    def row_values(self, aggregate: AggregateT) -> dict[str, object]:
        """1行に書く値（検索列と payload）を組み立てる。"""
        return {
            **self.search_columns(aggregate),
            "payload": encode_aggregate(aggregate),
        }

    def identity(self, values: Mapping[str, object]) -> uuid.UUID:
        """行の値から集約IDを取り出す。"""
        aggregate_id = values.get("id")
        if not isinstance(aggregate_id, uuid.UUID):
            raise PersistenceMappingError(
                f"{self.label}の id 列が UUID ではありません。"
            )
        return aggregate_id

    def decode(self, row: Mapping[str, object]) -> AggregateT:
        """payload から集約を復元し、検索列との食い違いを拒否する。

        列だけを直接書き換えられた行は、payload と食い違ったまま検索には
        引っかかる。集約として通すと、検索結果と中身が違う状態が業務処理へ
        流れ込むので、復元の時点で止める。
        """
        payload = row.get("payload")
        if not isinstance(payload, Mapping):
            raise PersistenceMappingError(
                f"{self.label}の payload が JSON オブジェクトではありません。"
            )
        aggregate = decode_aggregate(payload, self.aggregate_type)
        mismatched = sorted(
            name
            for name, expected in self.search_columns(aggregate).items()
            if not _column_matches(row.get(name), expected)
        )
        if mismatched:
            raise PersistenceMappingError(
                f"{self.label}の検索列と payload が一致しません: "
                f"{', '.join(mismatched)}。"
            )
        return aggregate


# --------------------------------------------------------------------------
# Repository 基底
# --------------------------------------------------------------------------


class PostgresRepositoryBase:
    """Unit of Work が管理するセッションで集約を読み書きする基底クラス。

    集約の読み書きは :meth:`find_one` / :meth:`find_all` / :meth:`save_aggregate`
    だけを通す。**世代の記録を呼び出し側の作法に委ねない。** 委ねると、記録を
    忘れた読み取り経路だけ楽観ロックの期待値が空になり、その経路の保存が後勝ちの
    上書きになる。例外も出ないので、実DBで同時更新が起きるまで誰も気づかない。
    そのため世代を記録する手続きと ``upsert`` は非公開にしてある。
    """

    def __init__(self, unit_of_work: PostgresUnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    @property
    def session(self) -> AsyncSession:
        """現在の Unit of Work のセッションを返す。"""
        return self._unit_of_work.session

    async def find_one[AggregateT](
        self,
        mapping: AggregateMapping[AggregateT],
        statement: Select[Any],
    ) -> AggregateT | None:
        """1行を読み、集約へ復元する。該当が無ければ ``None``。"""
        result = await self.session.execute(statement)
        row = result.mappings().one_or_none()
        if row is None:
            return None
        return self._restore(mapping, cast(Mapping[str, object], row))

    async def find_all[AggregateT](
        self,
        mapping: AggregateMapping[AggregateT],
        statement: Select[Any],
    ) -> list[AggregateT]:
        """複数行を読み、集約の一覧へ復元する。"""
        result = await self.session.execute(statement)
        return [
            self._restore(mapping, cast(Mapping[str, object], row))
            for row in result.mappings().all()
        ]

    async def save_aggregate[AggregateT](
        self,
        mapping: AggregateMapping[AggregateT],
        aggregate: AggregateT,
    ) -> None:
        """集約を1行として原子的に登録または更新する。

        Raises:
            ConcurrentModificationError: 読み込み後に別トランザクションが同じ行を
                更新していた場合、または未読の集約が既に存在していた場合。
            sqlalchemy.exc.IntegrityError: 一意制約・排他制約に違反した場合。どの
                制約をどの業務例外へ写像するかは呼び出し側のRepositoryが決める。
        """
        values = mapping.row_values(aggregate)
        await self._upsert(
            mapping.table,
            aggregate_id=mapping.identity(values),
            values=values,
        )

    def _restore[AggregateT](
        self,
        mapping: AggregateMapping[AggregateT],
        row: Mapping[str, object],
    ) -> AggregateT:
        """行の世代を記録してから集約へ復元する。"""
        self._remember_version(row, namespace=mapping.table.name)
        return mapping.decode(row)

    def _remember_version(self, row: Mapping[str, object], *, namespace: str) -> None:
        """読み込んだ行の世代を、保存時の期待値として記録する。

        ``namespace`` は同じ UUID を持つ別テーブルの集約と世代を分離する。
        """
        aggregate_id = row.get("id")
        version = row.get("version")
        if not isinstance(aggregate_id, uuid.UUID) or not isinstance(version, int):
            raise PersistenceMappingError(
                "永続化された行に id と version がありません。"
            )
        self._unit_of_work.remember_loaded_version(
            aggregate_id,
            version,
            namespace=namespace,
        )

    async def _upsert(
        self,
        table: Table,
        *,
        aggregate_id: uuid.UUID,
        values: Mapping[str, object],
    ) -> None:
        """1行を原子的に登録または更新する。

        事前の ``SELECT`` で存在を確かめてから ``INSERT`` / ``UPDATE`` を分けると、
        同一IDの同時保存で両方が「存在しない」を見て両方 ``INSERT`` し、主キー違反が
        素の ``IntegrityError`` として漏れる。``ON CONFLICT`` なら1文で決まる。

        更新は、このトランザクションで読み込んだ世代と一致する行だけを対象にする。
        一致しなければ更新対象が0行になり、後勝ちの上書き（lost update）ではなく
        :class:`ConcurrentModificationError` になる。
        """
        # 監査時刻は PostgreSQL の UTC セッション時刻で INSERT/UPDATE に統一する。
        # Application の Clock は業務日・記録時刻などのドメイン入力にだけ使う。
        now = func.now()
        namespace = table.name
        expected_version = self._unit_of_work.loaded_version(
            aggregate_id,
            namespace=namespace,
        )
        next_version = 1 if expected_version is None else expected_version + 1
        assignments = {**values, "version": next_version, "updated_at": now}

        statement = postgres_insert(table).values(**assignments, created_at=now)
        if expected_version is None:
            statement = statement.on_conflict_do_nothing(index_elements=[table.c.id])
        else:
            statement = statement.on_conflict_do_update(
                index_elements=[table.c.id],
                set_=assignments,
                where=table.c.version == expected_version,
            )

        result = cast(CursorResult[Any], await self.session.execute(statement))
        if result.rowcount == 0:
            raise ConcurrentModificationError()
        self._unit_of_work.record_version(
            aggregate_id,
            next_version,
            namespace=namespace,
        )


__all__ = [
    "AggregateMapping",
    "PostgresRepositoryBase",
    "closed_date_range_matches",
    "constraint_name",
]
