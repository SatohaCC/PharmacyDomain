"""Applicationのreferencessを定義する。"""

from __future__ import annotations

from typing import Protocol

from app.domain.care_event.identifiers import EventId
from app.domain.corporate.identifiers import CorporateId
from app.domain.dispensing.identifiers import DispensingId
from app.domain.patient.identifiers import PatientId
from app.domain.prescription.identifiers import PrescriptionId
from app.domain.reception.identifiers import ReceptionId
from app.domain.store.identifiers import StoreId


class EventPatientBoundary(Protocol):
    """法人に属する患者IDの存在を検証する。"""

    async def require_exists(
        self, *, corporate_id: CorporateId, patient_id: PatientId
    ) -> None: ...


class EventReceptionBoundary(Protocol):
    """ReceptionをEventへ関連付けるための整合確認と保存境界。"""

    async def validate_reference(
        self,
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
        reception_id: ReceptionId,
        patient_id: PatientId,
        prescription_id: PrescriptionId | None,
        dispensing_id: DispensingId | None,
    ) -> None: ...

    async def associate_event(
        self,
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
        reception_id: ReceptionId,
        event_id: EventId,
    ) -> None: ...


class EventMedicationHistoryBoundary(Protocol):
    """Eventに関連する薬歴IDだけを参照する。"""

    async def get_id(
        self, *, corporate_id: CorporateId, event_id: EventId
    ) -> str | None: ...
