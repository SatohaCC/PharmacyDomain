"""Reception Applicationが依存する参照境界。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.domain.corporate.identifiers import CorporateId
from app.domain.dispensing.identifiers import DispensingId
from app.domain.medication_history.identifiers import MedicationHistoryRecordId
from app.domain.patient.identifiers import PatientId
from app.domain.prescription.identifiers import PrescriptionId


@dataclass(frozen=True, kw_only=True)
class MedicationHistoryAssociationReference:
    """受付との関連確認に必要な薬歴の識別情報。"""

    id: MedicationHistoryRecordId
    patient_id: PatientId
    dispensing_id: DispensingId | None
    prescription_id: PrescriptionId | None


class MedicationHistoryAssociationBoundary(Protocol):
    """薬歴集約を保持せず、受付との関連に必要な識別情報を返す境界。"""

    async def get_for_association(
        self,
        *,
        corporate_id: CorporateId,
        record_id: MedicationHistoryRecordId,
    ) -> MedicationHistoryAssociationReference | None:
        """法人境界を適用し、指定薬歴の関連確認用情報を返す。"""
        ...
