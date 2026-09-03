"""適用資格選択履歴の PostgreSQL Repository。

履歴なので一意性制約を課さない。同じ患者に何度でも積み上がり、最新の1件は
次回受付の初期候補にしかならない（適用日ごとに再検証してから使う）。
"""

from __future__ import annotations

from sqlalchemy import select

from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientId
from app.domain.reception.coverage_selection_record import CoverageSelectionRecord
from app.domain.reception.primitives import CoverageSelectionRecordId
from app.domain.reception.repository import CoverageSelectionRecordRepository
from app.domain.store.primitives import StoreId
from app.infrastructure.postgres.repository_base import (
    AggregateMapping,
    PostgresRepositoryBase,
)
from app.infrastructure.postgres.schema import coverage_selection_records


def _selection_record_columns(record: CoverageSelectionRecord) -> dict[str, object]:
    """検索に使う列を履歴から導く。

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
    }


COVERAGE_SELECTION_RECORD_MAPPING = AggregateMapping(
    table=coverage_selection_records,
    aggregate_type=CoverageSelectionRecord,
    label="資格選択履歴",
    search_columns=_selection_record_columns,
)


class PostgresCoverageSelectionRecordRepository(
    PostgresRepositoryBase, CoverageSelectionRecordRepository
):
    """適用資格選択履歴を PostgreSQL へ保存・検索する。"""

    async def save(self, record: CoverageSelectionRecord) -> None:
        """履歴を保存する。履歴なので一意性制約は課さない。"""
        await self.save_aggregate(COVERAGE_SELECTION_RECORD_MAPPING, record)

    async def get(
        self,
        *,
        corporate_id: CorporateId,
        record_id: CoverageSelectionRecordId,
    ) -> CoverageSelectionRecord | None:
        """法人境界を含めてIDで履歴を検索する。"""
        return await self.find_one(
            COVERAGE_SELECTION_RECORD_MAPPING,
            select(coverage_selection_records).where(
                coverage_selection_records.c.corporate_id == corporate_id.value,
                coverage_selection_records.c.id == record_id.value,
            ),
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
        return await self.find_one(
            COVERAGE_SELECTION_RECORD_MAPPING,
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
            .limit(1),
        )
