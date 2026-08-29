"""PostgreSQL Repository 共通処理。"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from datetime import date, timedelta
from typing import Any, cast

from sqlalchemy import CursorResult, Table, func
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.foundation.exceptions import ConcurrentModificationError
from app.infrastructure.postgres.codec import PersistenceMappingError
from app.infrastructure.postgres.unit_of_work import PostgresUnitOfWork


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

    actual_upper = actual_range.upper
    if actual_upper is None:
        normalized_actual_upper: date | None = None
    elif actual_range.upper_inc:
        normalized_actual_upper = actual_upper
    else:
        normalized_actual_upper = actual_upper - timedelta(days=1)

    expected_upper = expected.upper
    if expected_upper is None:
        normalized_expected_upper: date | None = None
    elif expected.upper_inc:
        normalized_expected_upper = expected_upper
    else:
        normalized_expected_upper = expected_upper - timedelta(days=1)
    return normalized_actual_upper == normalized_expected_upper


class PostgresRepositoryBase:
    """Unit of Work が管理するセッションへアクセスする基底クラス。"""

    def __init__(self, unit_of_work: PostgresUnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    @property
    def session(self) -> AsyncSession:
        """現在の Unit of Work のセッションを返す。"""
        return self._unit_of_work.session

    def remember_version(
        self,
        row: Mapping[str, object],
        *,
        namespace: str = "",
    ) -> Mapping[str, object]:
        """読み込んだ行の世代を記録し、行をそのまま返す。

        保存時の期待値になるので、集約を復元する経路は必ずここを通す。
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
        return row

    async def upsert(
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

        Raises:
            ConcurrentModificationError: 読み込み後に別トランザクションが同じ行を
                更新していた場合、または未読の集約が既に存在していた場合。
            sqlalchemy.exc.IntegrityError: 一意制約に違反した場合。どの制約を
                どの業務例外へ写像するかは呼び出し側のRepositoryが決める。
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
