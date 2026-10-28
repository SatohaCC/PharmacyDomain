"""Applicationのvaluesを定義する。"""

from __future__ import annotations

from dataclasses import dataclass

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
