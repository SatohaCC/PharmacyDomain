"""業務Eventの参照Boundaryへ既存コンテキストを接続する。"""

from app.application.access_control.exceptions import TenantBoundaryNotFoundError
from app.application.care_event.references import (
    EventMedicationHistoryBoundary,
    EventPatientBoundary,
    EventReceptionBoundary,
)
from app.application.common.optional_conversion import unwrap
from app.application.medication_history.reference import (
    MedicationHistoryEventBoundary,
    MedicationHistoryEventReference,
)
from app.domain.care_event.primitives import EventId
from app.domain.care_event.repository import EventRepository
from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing.primitives import DispensingId
from app.domain.foundation.exceptions import DomainError
from app.domain.medication_history.repository import MedicationHistoryRepository
from app.domain.patient.primitives import PatientId
from app.domain.patient.repository import PatientRepository
from app.domain.prescription.primitives import PrescriptionId
from app.domain.reception.primitives import ReceptionId
from app.domain.reception.repository import ReceptionRepository
from app.domain.store.primitives import StoreId


class EventPatientReferenceAdapter(EventPatientBoundary):
    """Event作成時の患者存在確認を患者Repositoryへ委譲する。"""

    def __init__(self, patients: PatientRepository) -> None:
        self._patients = patients

    async def require_exists(
        self, *, corporate_id: CorporateId, patient_id: PatientId
    ) -> None:
        patient = await self._patients.get(
            corporate_id=corporate_id,
            patient_id=patient_id,
        )
        if patient is None:
            raise TenantBoundaryNotFoundError()


class EventMedicationHistoryReferenceAdapter(EventMedicationHistoryBoundary):
    """Event詳細へ薬歴IDだけを接続する。"""

    def __init__(self, histories: MedicationHistoryRepository) -> None:
        self._histories = histories

    async def get_id(
        self, *, corporate_id: CorporateId, event_id: EventId
    ) -> str | None:
        history = await self._histories.get_by_event(
            corporate_id=corporate_id,
            event_id=event_id,
        )
        return str(history.id.value) if history is not None else None


class MedicationHistoryEventReferenceAdapter(MedicationHistoryEventBoundary):
    """薬歴作成が必要とするEvent項目だけをEvent Repositoryから返す。"""

    def __init__(self, events: EventRepository) -> None:
        self._events = events

    async def get(
        self, *, corporate_id: CorporateId, event_id: EventId
    ) -> MedicationHistoryEventReference | None:
        event = await self._events.get(
            corporate_id=corporate_id,
            event_id=event_id,
        )
        if event is None:
            return None
        return MedicationHistoryEventReference(
            id=event.id,
            corporate_id=event.corporate_id,
            store_id=event.store_id,
            patient_id=event.patient_id,
            event_type_id=event.event_type_id,
            event_type_standard_code=unwrap(event.event_type_standard_code),
            event_type_name=event.event_type_name,
            occurred_at=event.occurred_at,
            reception_id=event.reception_id,
            prescription_id=event.prescription_id,
            dispensing_id=event.dispensing_id,
        )


class EventReceptionReferenceAdapter(EventReceptionBoundary):
    """Eventから参照する受付の整合性を検証して同じUoWで更新する。"""

    def __init__(self, receptions: ReceptionRepository) -> None:
        self._receptions = receptions

    async def validate_reference(
        self,
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
        reception_id: ReceptionId,
        patient_id: PatientId,
        prescription_id: PrescriptionId | None,
        dispensing_id: DispensingId | None,
    ) -> None:
        reception = await self._receptions.get(
            corporate_id=corporate_id,
            store_id=store_id,
            reception_id=reception_id,
        )
        if reception is None:
            raise TenantBoundaryNotFoundError()
        if reception.event_id is not None:
            raise DomainError("受付にはすでにEventが関連付いています。")
        if reception.patient_id != patient_id:
            raise DomainError("受付とEventの患者が一致しません。")
        if reception.prescription_id != prescription_id:
            raise DomainError("受付とEventの処方箋が一致しません。")
        if reception.dispensing_id != dispensing_id:
            raise DomainError("受付とEventの調剤セッションが一致しません。")

    async def associate_event(
        self,
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
        reception_id: ReceptionId,
        event_id: EventId,
    ) -> None:
        reception = await self._receptions.get(
            corporate_id=corporate_id,
            store_id=store_id,
            reception_id=reception_id,
        )
        if reception is None:
            raise TenantBoundaryNotFoundError()
        await self._receptions.save(reception.associate_event(event_id))


__all__ = [
    "EventMedicationHistoryReferenceAdapter",
    "EventPatientReferenceAdapter",
    "EventReceptionReferenceAdapter",
    "MedicationHistoryEventReferenceAdapter",
]
