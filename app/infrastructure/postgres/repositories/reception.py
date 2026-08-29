"""適用資格選択履歴の PostgreSQL Repository。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from sqlalchemy import select

from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientId
from app.domain.reception.coverage_selection_record import CoverageSelectionRecord
from app.domain.reception.primitives import CoverageSelectionRecordId
from app.domain.reception.repository import CoverageSelectionRecordRepository
from app.domain.store.primitives import StoreId
from app.infrastructure.postgres.codec import (
    PersistenceMappingError,
    decode_aggregate,
    encode_aggregate,
)
from app.infrastructure.postgres.repository_base import PostgresRepositoryBase
from app.infrastructure.postgres.schema import coverage_selection_records


def row_values(record: CoverageSelectionRecord) -> dict[str, object]:
    """集約から、payload と検索用の列を組み立てる。

    ``selection`` は枠構造のまま payload へ入れる。元資格IDと請求固定値を
    別々の列へ平坦化すると、両者の対応が並び順の規約になってしまう。
    """
    return {
        "id": record.id.value,
        "corporate_id": record.corporate_id.value,
        "store_id": record.store_id.value,
        "patient_id": record.patient_id.value,
        "applied_on": record.applied_on.value,
        "recorded_at": record.recorded_at.value,
        "payload": encode_aggregate(record),
    }


class PostgresCoverageSelectionRecordRepository(
    PostgresRepositoryBase, CoverageSelectionRecordRepository
):
    """適用資格選択履歴を PostgreSQL へ保存・検索する。"""

    async def save(self, record: CoverageSelectionRecord) -> None:
        """履歴を保存する。履歴なので一意性制約は課さない。"""
        await self.upsert(
            coverage_selection_records,
            aggregate_id=record.id.value,
            values=row_values(record),
        )

    async def get(
        self,
        *,
        corporate_id: CorporateId,
        record_id: CoverageSelectionRecordId,
    ) -> CoverageSelectionRecord | None:
        """法人境界を含めてIDで履歴を検索する。"""
        result = await self.session.execute(
            select(coverage_selection_records).where(
                coverage_selection_records.c.corporate_id == corporate_id.value,
                coverage_selection_records.c.id == record_id.value,
            )
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None
        return _decode_row(
            self.remember_version(
                cast(Mapping[str, object], row),
                namespace=coverage_selection_records.name,
            )
        )

    async def get_latest(
        self,
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
        patient_id: PatientId,
    ) -> CoverageSelectionRecord | None:
        """``(recorded_at, id)`` の降順で最新の履歴を取得する。

        記録時刻が同着でも順序が決まるよう、契約どおりIDを第2キーにする。
        """
        result = await self.session.execute(
            select(coverage_selection_records)
            .where(
                coverage_selection_records.c.corporate_id == corporate_id.value,
                coverage_selection_records.c.store_id == store_id.value,
                coverage_selection_records.c.patient_id == patient_id.value,
            )
            .order_by(
                coverage_selection_records.c.recorded_at.desc(),
                coverage_selection_records.c.id.desc(),
            )
            .limit(1)
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None
        return _decode_row(
            self.remember_version(
                cast(Mapping[str, object], row),
                namespace=coverage_selection_records.name,
            )
        )


def _decode_row(row: Mapping[str, object]) -> CoverageSelectionRecord:
    """DB行の検索列と payload の整合性を確認して復元する。"""
    payload = row.get("payload")
    if not isinstance(payload, Mapping):
        raise PersistenceMappingError(
            "資格選択履歴の payload が JSON オブジェクトではありません。"
        )
    record = decode_aggregate(payload, CoverageSelectionRecord)
    if (
        record.id.value != row.get("id")
        or record.corporate_id.value != row.get("corporate_id")
        or record.store_id.value != row.get("store_id")
        or record.patient_id.value != row.get("patient_id")
        or record.applied_on.value != row.get("applied_on")
        or record.recorded_at.value != row.get("recorded_at")
    ):
        raise PersistenceMappingError("資格選択履歴の検索列と payload が一致しません。")
    return record
