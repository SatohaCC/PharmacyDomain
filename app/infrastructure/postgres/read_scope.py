"""許可店舗をSQLの取得条件へ含めるリクエスト単位の読取範囲。"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Any, Final
from uuid import UUID

from sqlalchemy import Select, Table, cast, exists, func, or_, select
from sqlalchemy.dialects.postgresql import JSONB


class ReadScopeKind(StrEnum):
    """店舗ロールに対して、そのテーブルをどこまで見せるか。"""

    #: 非テナントの参照マスタ。誰が読んでも同じ内容になる。
    GLOBAL = "global"
    #: 自法人の行だけ。
    CORPORATE = "corporate"
    #: 自法人かつ許可店舗の行だけ。
    STORE = "store"
    #: ``corporates`` 自身。行のIDが自法人であること。
    CORPORATE_ITSELF = "corporate_itself"
    #: ``stores`` 自身。行のIDが許可店舗であること。
    STORE_ITSELF = "store_itself"
    #: 適用日時点で許可店舗に所属しているスタッフだけ。
    STAFF_AFFILIATION = "staff_affiliation"
    #: 自分のアカウント行だけ。
    OWN_ACCOUNT = "own_account"
    #: 自分の本人行だけ。
    OWN_PERSON = "own_person"


#: 各テーブルの読取範囲。
#:
#: 表に無いテーブルは素通りさせない。以前は「テーブル名と列名のどれにも当たら
#: なければ条件を付けない」という既定だったため、新しいテーブルを足した時点で
#: 店舗ロールに全件が見える状態になり、しかもそれを知らせるものが何も無かった。
#: 判断を保留できる欄を作らず、追加したら必ずここへ1行書かせる。
READ_SCOPE_KINDS: Final[Mapping[str, ReadScopeKind]] = {
    # 薬価基準は国が定めるので法人ごとに内容が違わない。
    "medicines": ReadScopeKind.GLOBAL,
    "corporates": ReadScopeKind.CORPORATE_ITSELF,
    "stores": ReadScopeKind.STORE_ITSELF,
    "staff_members": ReadScopeKind.STAFF_AFFILIATION,
    "account_people": ReadScopeKind.OWN_PERSON,
    "user_accounts": ReadScopeKind.OWN_ACCOUNT,
    # 法人内で完結する台帳。店舗をまたいで同じ患者を扱うので店舗では絞らない。
    "patients": ReadScopeKind.CORPORATE,
    "patient_number_sequences": ReadScopeKind.CORPORATE,
    "patient_external_identifiers": ReadScopeKind.CORPORATE,
    "patient_coverages": ReadScopeKind.CORPORATE,
    "patient_medical_profiles": ReadScopeKind.CORPORATE,
    "medication_history_category_catalogs": ReadScopeKind.CORPORATE,
    "corporate_memberships": ReadScopeKind.CORPORATE,
    "user_invitations": ReadScopeKind.CORPORATE,
    "staff_person_links": ReadScopeKind.CORPORATE,
    # 店舗で発生する記録。
    "prescriptions": ReadScopeKind.STORE,
    "dispensing_processes": ReadScopeKind.STORE,
    "medication_history_records": ReadScopeKind.STORE,
    "coverage_selection_records": ReadScopeKind.STORE,
    "receptions": ReadScopeKind.STORE,
    "store_manager_assignments": ReadScopeKind.STORE,
    "operation_audits": ReadScopeKind.STORE,
}


class UnscopedTableError(RuntimeError):
    """読取範囲を宣言していないテーブルを、範囲付きで読もうとした。"""


@dataclass(frozen=True)
class RepositoryReadScope:
    """法人と許可店舗を検索時に限定し、取得後の絞り込みを避ける。"""

    corporate_id: UUID
    store_ids: tuple[UUID, ...]
    applied_on: date
    person_id: UUID
    account_id: UUID

    def apply(self, table: Table, statement: Select[Any]) -> Select[Any]:
        """テーブルごとに宣言された範囲を取得条件へ足す。

        Raises:
            UnscopedTableError: 範囲を宣言していないテーブルを読もうとした場合。
                「知らないテーブルは制限しない」に倒すと、テーブルを足した瞬間に
                店舗ロールへ全件が見える。
        """
        kind = READ_SCOPE_KINDS.get(table.name)
        if kind is None:
            raise UnscopedTableError(
                f"{table.name} の読取範囲が宣言されていません。"
                "READ_SCOPE_KINDS へ追加してください。"
            )
        if kind is ReadScopeKind.GLOBAL:
            return statement
        if kind is ReadScopeKind.CORPORATE_ITSELF:
            return statement.where(table.c.id == self.corporate_id)
        if kind is ReadScopeKind.OWN_PERSON:
            return statement.where(table.c.id == self.person_id)
        if kind is ReadScopeKind.OWN_ACCOUNT:
            return statement.where(table.c.id == self.account_id)

        statement = statement.where(table.c.corporate_id == self.corporate_id)
        if kind is ReadScopeKind.CORPORATE:
            return statement
        if kind is ReadScopeKind.STORE_ITSELF:
            return statement.where(table.c.id.in_(self.store_ids))
        if kind is ReadScopeKind.STORE:
            return statement.where(table.c.store_id.in_(self.store_ids))
        return statement.where(exists(self._visible_affiliation(table)))

    def _visible_affiliation(self, table: Table) -> Select[Any]:
        """適用日に許可店舗へ所属している行だけを選ぶ相関副問い合わせ。"""
        affiliations = (
            func.jsonb_array_elements(table.c.payload["affiliations"])
            .table_valued("value")
            .alias("visible_affiliation")
        )
        item = cast(affiliations.c.value, JSONB)
        period = item["period"]
        return (
            select(1)
            .select_from(affiliations)
            .where(
                item["store_id"].astext.in_([str(value) for value in self.store_ids]),
                period["start_date"].astext <= self.applied_on.isoformat(),
                or_(
                    period["end_date"].astext.is_(None),
                    period["end_date"].astext >= self.applied_on.isoformat(),
                ),
            )
        )


__all__ = [
    "READ_SCOPE_KINDS",
    "ReadScopeKind",
    "RepositoryReadScope",
    "UnscopedTableError",
]
