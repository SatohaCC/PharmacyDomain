"""Applicationのreferenceを定義する。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.application.medication_history.commands.models import BillingAdditionInput
from app.domain.care_event.identifiers import EventId
from app.domain.dispensing.identifiers import DispensingId
from app.domain.medication_history.identifiers import MedicationHistoryRecordId
from app.domain.patient.identifiers import PatientId
from app.domain.prescription.identifiers import PrescriptionId


@dataclass(frozen=True, kw_only=True)
class ReceptionMedicationHistorySource:
    """初回保存へ引き継ぐ受付由来情報。"""

    patient_id: PatientId
    prescription_id: PrescriptionId | None
    dispensing_id: DispensingId | None
    event_id: EventId | None
    medication_history_id: MedicationHistoryRecordId | None
    source_system: str | None
    imported_at: datetime | None
    is_follow_up: bool
    billing_additions: tuple[BillingAdditionInput, ...]
