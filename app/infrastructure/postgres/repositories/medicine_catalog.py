"""医薬品マスタの PostgreSQL Repository。

**法人IDを取らない。** 薬価基準は国が定めるので法人ごとに内容が違わない。
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.exc import IntegrityError

from app.domain.medicine_catalog.exceptions import (
    MedicineEffectivePeriodConflictError,
)
from app.domain.medicine_catalog.medicine import Medicine
from app.domain.medicine_catalog.primitives import MedicineCatalogEntryId
from app.domain.medicine_catalog.repository import MedicineCatalogRepository
from app.domain.shared.medicine import MedicineIdentifier
from app.infrastructure.postgres.repository_base import (
    AggregateMapping,
    PostgresRepositoryBase,
    constraint_name,
)
from app.infrastructure.postgres.schema import medicines


def identifier_key(identifier: MedicineIdentifier) -> str:
    """薬品コードの同一性を、NULLを含まない1つの文字列で表す。

    排他制約の ``=`` は NULL 同士を等しいと扱わないため、``code`` が未設定の行が
    互いに衝突しなくなる。ドメインの ``MedicineIdentifier`` の等価性は
    「種別とコードの組が等しい」なので、その組をそのまま文字列にして揃える。
    """
    code = "" if identifier.code is None else identifier.code.value
    return f"{identifier.code_type.value}:{code}"


def effective_range(medicine: Medicine) -> Range[date]:
    """収載期間を PostgreSQL の日付範囲へ変換する。

    ``MedicineEffectivePeriod`` は経過措置期限を**含む**閉区間なので境界は
    ``[]`` にする。半開区間にすると期限当日の調剤を誤って弾く。
    """
    period = medicine.effective_period
    upper = None if period.withdrawn_on is None else period.withdrawn_on.value
    return Range(period.listed_on.value, upper, bounds="[]")


def _search_columns(medicine: Medicine) -> dict[str, object]:
    """検索・競合判定に使う列を集約から導く。"""
    period = medicine.effective_period
    return {
        "id": medicine.id.value,
        "identifier_key": identifier_key(medicine.identifier),
        "code_type": medicine.identifier.code_type.value,
        "code": (
            None if medicine.identifier.code is None else medicine.identifier.code.value
        ),
        "listed_on": period.listed_on.value,
        "withdrawn_on": (
            None if period.withdrawn_on is None else period.withdrawn_on.value
        ),
        "effective_range": effective_range(medicine),
    }


MEDICINE_MAPPING = AggregateMapping(
    table=medicines,
    aggregate_type=Medicine,
    label="医薬品マスタ",
    search_columns=_search_columns,
)


class PostgresMedicineCatalogRepository(
    PostgresRepositoryBase, MedicineCatalogRepository
):
    """医薬品マスタを PostgreSQL へ保存・検索する。"""

    async def get(self, entry_id: MedicineCatalogEntryId) -> Medicine | None:
        """マスタ行を識別子で取得する。"""
        return await self.find_one(
            MEDICINE_MAPPING,
            select(medicines).where(medicines.c.id == entry_id.value),
        )

    async def find_effective(
        self,
        *,
        identifier: MedicineIdentifier,
        as_of: date,
    ) -> Medicine | None:
        """指定日に有効なマスタ行を返す。

        適用日で範囲に含まれる行を引く。期間が重なる行は排他制約により存在
        しないので、戻り値は一意に定まる。
        """
        return await self.find_one(
            MEDICINE_MAPPING,
            select(medicines).where(
                medicines.c.identifier_key == identifier_key(identifier),
                medicines.c.effective_range.contains(as_of),
            ),
        )

    async def list_versions(self, identifier: MedicineIdentifier) -> list[Medicine]:
        """同じ薬品コードの全ての行を収載日の昇順で返す。"""
        return await self.find_all(
            MEDICINE_MAPPING,
            select(medicines)
            .where(medicines.c.identifier_key == identifier_key(identifier))
            .order_by(medicines.c.listed_on, medicines.c.id),
        )

    async def save(self, medicine: Medicine) -> None:
        """同一薬品コードの収載期間の重複を原子的に拒否して保存する。"""
        try:
            await self.save_aggregate(MEDICINE_MAPPING, medicine)
        except IntegrityError as error:
            if constraint_name(error) == "excl_medicines_effective_period":
                code = medicine.identifier.code
                raise MedicineEffectivePeriodConflictError(
                    medicine_code=code.value if code is not None else None
                ) from error
            raise
