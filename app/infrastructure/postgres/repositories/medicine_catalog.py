"""医薬品マスタの PostgreSQL Repository。

**法人IDを取らない。** 薬価基準は国が定めるので法人ごとに内容が違わない。
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import cast

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
from app.infrastructure.postgres.codec import (
    PersistenceMappingError,
    decode_aggregate,
    encode_aggregate,
)
from app.infrastructure.postgres.constraints import constraint_name
from app.infrastructure.postgres.repository_base import (
    PostgresRepositoryBase,
    closed_date_range_matches,
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


def row_values(medicine: Medicine) -> dict[str, object]:
    """集約から、payload と検索・競合判定用の列を組み立てる。"""
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
        "payload": encode_aggregate(medicine),
    }


class PostgresMedicineCatalogRepository(
    PostgresRepositoryBase, MedicineCatalogRepository
):
    """医薬品マスタを PostgreSQL へ保存・検索する。"""

    async def get(self, entry_id: MedicineCatalogEntryId) -> Medicine | None:
        """マスタ行を識別子で取得する。"""
        result = await self.session.execute(
            select(medicines).where(medicines.c.id == entry_id.value)
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None
        return _decode_row(
            self.remember_version(
                cast(Mapping[str, object], row),
                namespace=medicines.name,
            )
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
        result = await self.session.execute(
            select(medicines).where(
                medicines.c.identifier_key == identifier_key(identifier),
                medicines.c.effective_range.contains(as_of),
            )
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None
        return _decode_row(
            self.remember_version(
                cast(Mapping[str, object], row),
                namespace=medicines.name,
            )
        )

    async def list_versions(self, identifier: MedicineIdentifier) -> list[Medicine]:
        """同じ薬品コードの全ての行を収載日の昇順で返す。"""
        result = await self.session.execute(
            select(medicines)
            .where(medicines.c.identifier_key == identifier_key(identifier))
            .order_by(medicines.c.listed_on, medicines.c.id)
        )
        return [
            _decode_row(
                self.remember_version(
                    cast(Mapping[str, object], row),
                    namespace=medicines.name,
                )
            )
            for row in result.mappings().all()
        ]

    async def save(self, medicine: Medicine) -> None:
        """同一薬品コードの収載期間の重複を原子的に拒否して保存する。"""
        try:
            await self.upsert(
                medicines, aggregate_id=medicine.id.value, values=row_values(medicine)
            )
        except IntegrityError as error:
            if constraint_name(error) == "excl_medicines_effective_period":
                code = medicine.identifier.code
                raise MedicineEffectivePeriodConflictError(
                    medicine_code=code.value if code is not None else None
                ) from error
            raise


def _decode_row(row: Mapping[str, object]) -> Medicine:
    """DB行の検索列と payload の整合性を確認して復元する。"""
    payload = row.get("payload")
    if not isinstance(payload, Mapping):
        raise PersistenceMappingError(
            "医薬品マスタの payload が JSON オブジェクトではありません。"
        )
    medicine = decode_aggregate(payload, Medicine)
    period = medicine.effective_period
    withdrawn_on = None if period.withdrawn_on is None else period.withdrawn_on.value
    if (
        medicine.id.value != row.get("id")
        or identifier_key(medicine.identifier) != row.get("identifier_key")
        or medicine.identifier.code_type.value != row.get("code_type")
        or (
            None if medicine.identifier.code is None else medicine.identifier.code.value
        )
        != row.get("code")
        or period.listed_on.value != row.get("listed_on")
        or withdrawn_on != row.get("withdrawn_on")
        or not closed_date_range_matches(
            row.get("effective_range"),
            effective_range(medicine),
        )
    ):
        raise PersistenceMappingError("医薬品マスタの検索列と payload が一致しません。")
    return medicine
