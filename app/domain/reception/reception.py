"""受付単位で受信した外部データの追跡枠。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing.primitives import DispensingId
from app.domain.foundation.entity import AggregateRoot
from app.domain.medication_history.primitives import MedicationHistoryRecordId
from app.domain.patient.primitives import PatientId
from app.domain.prescription.primitives import PrescriptionId
from app.domain.reception.primitives import (
    ReceptionFieldPath,
    ReceptionFingerprint,
    ReceptionId,
)
from app.domain.store.primitives import StoreId


@dataclass(frozen=True, kw_only=True)
class ReceptionCorrection:
    """受付に届いた訂正情報の記録。"""

    fingerprint: ReceptionFingerprint
    changed_fields: tuple[ReceptionFieldPath, ...]
    received_at: datetime


@dataclass(frozen=True, eq=False, kw_only=True)
class Reception(AggregateRoot[ReceptionId]):
    """一受付の受信指紋と作成済み集約IDを保持する。"""

    id: ReceptionId
    corporate_id: CorporateId
    store_id: StoreId
    patient_id: PatientId
    latest_fingerprint: ReceptionFingerprint
    field_fingerprints: tuple[tuple[ReceptionFieldPath, ReceptionFingerprint], ...]
    correction_history: tuple[ReceptionCorrection, ...] = ()
    prescription_id: PrescriptionId | None = None
    dispensing_id: DispensingId | None = None
    medication_history_id: MedicationHistoryRecordId | None = None
