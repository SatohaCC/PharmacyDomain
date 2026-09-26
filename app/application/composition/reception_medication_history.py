"""ReceptionからMedicationHistoryを参照するCompositionアダプタ。"""

from __future__ import annotations

from app.application.reception.reference import (
    MedicationHistoryAssociationBoundary,
    MedicationHistoryAssociationReference,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.medication_history.primitives import MedicationHistoryRecordId
from app.domain.medication_history.repository import MedicationHistoryRepository


class ReceptionMedicationHistoryAssociationAdapter(
    MedicationHistoryAssociationBoundary
):
    """Repositoryから受付との関連確認に必要な値だけを取り出す。"""

    def __init__(self, repository: MedicationHistoryRepository) -> None:
        self._repository = repository

    async def get_for_association(
        self,
        *,
        corporate_id: CorporateId,
        record_id: MedicationHistoryRecordId,
    ) -> MedicationHistoryAssociationReference | None:
        """別法人の記録を見せず、ID参照情報に変換して返す。"""
        record = await self._repository.get(
            corporate_id=corporate_id,
            record_id=record_id,
        )
        if record is None:
            return None
        return MedicationHistoryAssociationReference(
            id=record.id,
            patient_id=record.patient_id,
            dispensing_id=record.dispensing_id,
            prescription_id=record.prescription_id,
        )
