"""処方箋受付および外部システム（レセコン・NSIPS等）から届いた受付データの管理。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from app.domain.care_event.primitives import EventId
from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing.primitives import DispensingId
from app.domain.foundation.entity import AggregateRoot
from app.domain.medication_history.primitives import MedicationHistoryRecordId
from app.domain.patient.primitives import PatientId
from app.domain.prescription.primitives import PrescriptionId
from app.domain.reception.exceptions import ReceptionEventAlreadyAssociatedError
from app.domain.reception.primitives import (
    ReceptionFieldPath,
    ReceptionFingerprint,
    ReceptionId,
)
from app.domain.store.primitives import StoreId


@dataclass(frozen=True, kw_only=True)
class ReceptionCorrection:
    """レセコン等で修正された処方・受付内容の訂正履歴。"""

    fingerprint: ReceptionFingerprint
    changed_fields: tuple[ReceptionFieldPath, ...]
    received_at: datetime


@dataclass(frozen=True, kw_only=True)
class ReceptionBillingAddition:
    """受付時にレセコン側で算定された調剤報酬の加算項目（調剤基本料加算、地域支援体制加算、時間外加算等）。"""

    code: str
    name: str
    points: int | None = None
    quantity: int | None = None


@dataclass(frozen=True, kw_only=True)
class ReceptionSourceData:
    """外部システム（レセコン・NSIPS等）から受信した受付データ原本の控え。"""

    bundle_json: str
    imported_at: datetime
    is_follow_up: bool = False
    billing_additions: tuple[ReceptionBillingAddition, ...] = ()


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
