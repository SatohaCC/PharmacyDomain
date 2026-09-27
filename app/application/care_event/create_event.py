"""業務Event作成ユースケースの承認済み入口。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.application.access_control.boundary import CorporateAccessBoundary
from app.application.access_control.exceptions import TenantBoundaryNotFoundError
from app.application.access_control.models import Permission
from app.application.access_control.store_access import (
    StoreOperation,
    StoreOperationBoundary,
)
from app.application.care_event.references import (
    EventMedicationHistoryBoundary,
    EventPatientBoundary,
    EventReceptionBoundary,
)
from app.application.common.clock import Clock
from app.domain.care_event.event import Event
from app.domain.care_event.exceptions import EventAlreadyAssociatedError
from app.domain.care_event.primitives import (
    EventCreatedTimestamp,
    EventId,
    EventOccurredTimestamp,
    EventTypeId,
    EventTypeStandardCode,
)
from app.domain.care_event.repository import EventDefinitionRepository, EventRepository
from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing.primitives import DispensingId
from app.domain.foundation.exceptions import DomainError
from app.domain.patient.primitives import PatientId
from app.domain.prescription.primitives import PrescriptionId
from app.domain.reception.primitives import ReceptionId
from app.domain.store.primitives import StoreId


@dataclass(frozen=True, kw_only=True)
class CreateEventCommand:
    """業務Event作成のHTTP外入力。"""

    corporate_id: str
    store_id: str
    patient_id: str
    event_type_id: str
    occurred_at: datetime
    related_event_id: str | None = None
    reception_id: str | None = None
    prescription_id: str | None = None
    dispensing_id: str | None = None


@dataclass(frozen=True, kw_only=True)
class EventDto:
    """Eventと薬歴の有無を返すDTO。"""

    event_id: str
    medication_history_id: str | None
    event_type_id: str
    event_type_name: str
    corporate_id: str
    store_id: str
    patient_id: str
    occurred_at: str | None
    occurred_at_is_unknown: bool
    created_at: str
    related_event_id: str | None
    reception_id: str | None
    prescription_id: str | None
    dispensing_id: str | None

    @classmethod
    def from_entity(
        cls, event: Event, *, medication_history_id: str | None = None
    ) -> EventDto:
        """Eventを公開用のメタデータDTOへ変換する。"""
        return cls(
            event_id=str(event.id.value),
            medication_history_id=medication_history_id,
            event_type_id=str(event.event_type_id.value),
            event_type_name=event.event_type_name.value,
            corporate_id=str(event.corporate_id.value),
            store_id=str(event.store_id.value),
            patient_id=str(event.patient_id.value),
            occurred_at=(
                event.occurred_at.value.isoformat()
                if event.occurred_at is not None
                else None
            ),
            occurred_at_is_unknown=event.occurred_at_is_unknown,
            created_at=event.created_at.value.isoformat(),
            related_event_id=(
                str(event.related_event_id.value)
                if event.related_event_id is not None
                else None
            ),
            reception_id=(
                str(event.reception_id.value)
                if event.reception_id is not None
                else None
            ),
            prescription_id=(
                str(event.prescription_id.value)
                if event.prescription_id is not None
                else None
            ),
            dispensing_id=(
                str(event.dispensing_id.value)
                if event.dispensing_id is not None
                else None
            ),
        )


class CreateEventUseCase:
    """有効店舗でEventを作成する。"""

    def __init__(
        self,
        *,
        event_repository: EventRepository,
        event_definition_repository: EventDefinitionRepository,
        patient_boundary: EventPatientBoundary,
        corporate_access: CorporateAccessBoundary,
        store_operations: StoreOperationBoundary,
        clock: Clock,
        reception_boundary: EventReceptionBoundary | None = None,
        medication_history: EventMedicationHistoryBoundary | None = None,
    ) -> None:
        self._event_repository = event_repository
        self._event_definition_repository = event_definition_repository
        self._patient_boundary = patient_boundary
        self._corporate_access = corporate_access
        self._store_operations = store_operations
        self._clock = clock
        self._reception_boundary = reception_boundary
        self._medication_history = medication_history

    async def execute(self, command: CreateEventCommand) -> EventDto:
        """権限・店舗・患者・種別・関連元を検証してEventを保存する。"""
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.MANAGE_EVENT,
        )
        store_id = StoreId.parse(command.store_id)
        await self._store_operations.require_allowed(
            corporate_id=corporate_id,
            store_id=store_id,
            operation=StoreOperation.CREATE_EVENT,
        )
        patient_id = PatientId.parse(command.patient_id)
        await self._patient_boundary.require_exists(
            corporate_id=corporate_id,
            patient_id=patient_id,
        )
        event_type_id = EventTypeId.parse(command.event_type_id)
        definition = await self._event_definition_repository.get(
            corporate_id=corporate_id,
            event_type_id=event_type_id,
        )
        if definition is None:
            raise TenantBoundaryNotFoundError()
        if not definition.is_active:
            raise DomainError("無効なイベント種別は新規Eventに使用できません。")

        related_event_id = (
            EventId.parse(command.related_event_id)
            if command.related_event_id is not None
            else None
        )
        if related_event_id is not None:
            related = await self._event_repository.get_related(
                corporate_id=corporate_id,
                patient_id=patient_id,
                event_id=related_event_id,
            )
            if related is None:
                raise TenantBoundaryNotFoundError()

        reception_id = (
            ReceptionId.parse(command.reception_id)
            if command.reception_id is not None
            else None
        )
        prescription_id = (
            PrescriptionId.parse(command.prescription_id)
            if command.prescription_id is not None
            else None
        )
        dispensing_id = (
            DispensingId.parse(command.dispensing_id)
            if command.dispensing_id is not None
            else None
        )
        if reception_id is not None:
            existing = await self._event_repository.get_by_reception(
                corporate_id=corporate_id,
                store_id=store_id,
                reception_id=reception_id,
            )
            requested_occurred_at = EventOccurredTimestamp(command.occurred_at)
            if existing is not None:
                if (
                    existing.event_type_id != definition.id
                    or existing.patient_id != patient_id
                    or existing.occurred_at != requested_occurred_at
                    or existing.prescription_id != prescription_id
                    or existing.dispensing_id != dispensing_id
                ):
                    raise EventAlreadyAssociatedError()
                history_id = (
                    await self._medication_history.get_id(
                        corporate_id=corporate_id,
                        event_id=existing.id,
                    )
                    if self._medication_history is not None
                    else None
                )
                return EventDto.from_entity(
                    existing,
                    medication_history_id=history_id,
                )
            if definition.standard_code != EventTypeStandardCode(
                "prescription_reception"
            ):
                raise DomainError("Receptionは処方箋受付Eventだけに関連付けられます。")
            if self._reception_boundary is None:
                raise DomainError("受付とEventの整合性を確認できません。")
            await self._reception_boundary.validate_reference(
                corporate_id=corporate_id,
                store_id=store_id,
                reception_id=reception_id,
                patient_id=patient_id,
                prescription_id=prescription_id,
                dispensing_id=dispensing_id,
            )

        event = Event.create(
            event_type_id=definition.id,
            event_definition_corporate_id=definition.corporate_id,
            event_type_standard_code=definition.standard_code,
            event_type_name=definition.name,
            corporate_id=corporate_id,
            store_id=store_id,
            patient_id=patient_id,
            occurred_at=EventOccurredTimestamp(command.occurred_at),
            created_at=EventCreatedTimestamp(self._clock.now()),
            related_event_id=related_event_id,
            reception_id=reception_id,
            prescription_id=prescription_id,
            dispensing_id=dispensing_id,
        )
        await self._event_repository.save(event)
        if reception_id is not None:
            assert self._reception_boundary is not None
            await self._reception_boundary.associate_event(
                corporate_id=corporate_id,
                store_id=store_id,
                reception_id=reception_id,
                event_id=event.id,
            )
        return EventDto.from_entity(event)
