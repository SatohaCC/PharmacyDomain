"""receptionのエンティティと集約。"""

from __future__ import annotations

from dataclasses import dataclass, replace

from app.domain.care_event.identifiers import EventId
from app.domain.corporate.identifiers import CorporateId
from app.domain.dispensing.identifiers import DispensingId
from app.domain.foundation.entity import AggregateRoot
from app.domain.medication_history.identifiers import MedicationHistoryRecordId
from app.domain.patient.identifiers import PatientId
from app.domain.prescription.identifiers import PrescriptionId
from app.domain.reception.exceptions import ReceptionEventAlreadyAssociatedError
from app.domain.reception.identifiers import ReceptionId
from app.domain.reception.primitives import ReceptionFieldPath, ReceptionFingerprint
from app.domain.reception.value_objects import ReceptionCorrection, ReceptionSourceData
from app.domain.store.identifiers import StoreId


@dataclass(frozen=True, eq=False, kw_only=True)
class Reception(AggregateRoot[ReceptionId]):
    """処方箋受付の1回分を管理し、受付から作成される処方箋原本・調剤・薬歴への対応関係を保持するエンティティ。"""

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
    source_data: ReceptionSourceData | None = None
    source_data_history: tuple[ReceptionSourceData, ...] = ()
    event_id: EventId | None = None

    def associate_event(self, event_id: EventId) -> Reception:
        """処方受付に対応する薬局業務イベント（調剤・服薬指導など）を一意に関連付ける。"""
        if self.event_id is not None and self.event_id != event_id:
            raise ReceptionEventAlreadyAssociatedError()
        return replace(self, event_id=event_id)
