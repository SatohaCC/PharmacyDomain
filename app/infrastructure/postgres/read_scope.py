"""許可店舗をSQLの取得条件へ含めるリクエスト単位の読取範囲。"""

from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import Select, Table, cast, exists, func, or_, select
from sqlalchemy.dialects.postgresql import JSONB


@dataclass(frozen=True)
class RepositoryReadScope:
    """法人と許可店舗を検索時に限定し、取得後の絞り込みを避ける。"""

    corporate_id: UUID
    store_ids: tuple[UUID, ...]
    applied_on: date

    def apply(self, table: Table, statement: Select[Any]) -> Select[Any]:
        """店舗を持つ記録と現在所属スタッフだけに条件を付ける。"""
        if "corporate_id" in table.c:
            statement = statement.where(table.c.corporate_id == self.corporate_id)
        if table.name == "stores":
            return statement.where(table.c.id.in_(self.store_ids))
        if "store_id" in table.c:
            return statement.where(table.c.store_id.in_(self.store_ids))
        if table.name == "staff_members":
            affiliations = (
                func.jsonb_array_elements(table.c.payload["affiliations"])
                .table_valued("value")
                .alias("visible_affiliation")
            )
            item = cast(affiliations.c.value, JSONB)
            period = item["period"]
            visible = (
                select(1)
                .select_from(affiliations)
                .where(
                    item["store_id"].astext.in_(
                        [str(value) for value in self.store_ids]
                    ),
                    period["start_date"].astext <= self.applied_on.isoformat(),
                    or_(
                        period["end_date"].astext.is_(None),
                        period["end_date"].astext >= self.applied_on.isoformat(),
                    ),
                )
            )
            return statement.where(exists(visible))
        return statement
