"""業務Eventユースケースのテスト組み立て。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.application.access_control.models import ActorRole, ResolvedActorContext
from app.application.access_control.policy import AuthorizationService
from app.application.care_event.create_event import (
    CreateEventCommand,
    CreateEventUseCase,
)
from app.application.care_event.list_related_candidates import (
    ListRelatedEventCandidatesUseCase,
)
from app.application.corporate.corporate_access import CorporateAccessService
from app.domain.care_event.event_definition import EventDefinition
from app.domain.care_event.primitives import (
    EventTypeId,
    EventTypeName,
    EventTypeStandardCode,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.identity.primitives import AccountPersonId, UserAccountId
from app.domain.patient.primitives import PatientId
from app.domain.staff.primitives import StaffId
from app.domain.store.primitives import StoreId
from tests.application.access_helpers import AutoProvisioningCorporateRepository
from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_event_patient_boundary import FakeEventPatientBoundary
from tests.fakes.fake_medication_history_store_operations import (
    FakeMedicationHistoryStoreOperations,
)
from tests.fakes.in_memory_event_definition_repository import (
    InMemoryEventDefinitionRepository,
)
from tests.fakes.in_memory_event_repository import InMemoryEventRepository


@dataclass(frozen=True, kw_only=True)
class EventFixture:
    create_event: CreateEventUseCase
    list_related_candidates: ListRelatedEventCandidatesUseCase
    event_repository: InMemoryEventRepository
    event_definition_repository: InMemoryEventDefinitionRepository
    patient_boundary: FakeEventPatientBoundary
    store_operations: FakeMedicationHistoryStoreOperations
    clock: FakeClock
    corporate_access: CorporateAccessService
    corporate_id: CorporateId
    store_id: StoreId
    patient_id: PatientId
    event_type_id: EventTypeId


def create_fixture(*, role: ActorRole = ActorRole.STORE_OPERATOR) -> EventFixture:
    corporate_id = CorporateId.generate()
    store_id = StoreId.generate()
    patient_id = PatientId.generate()
    event_type_id = EventTypeId.generate()
    actor = ResolvedActorContext(
        principal_id="業務Event担当者",
        roles=frozenset({role}),
        corporate_id=corporate_id,
        person_id=AccountPersonId.generate(),
        account_id=UserAccountId.generate(),
        staff_id=StaffId.generate(),
        store_ids=frozenset({store_id}),
    )
    access = CorporateAccessService(
        AutoProvisioningCorporateRepository(), AuthorizationService(actor)
    )
    event_repository = InMemoryEventRepository()
    definitions = InMemoryEventDefinitionRepository()
    definition = EventDefinition(
        id=event_type_id,
        name=EventTypeName("来局相談"),
        standard_code=EventTypeStandardCode("in_person_consultation"),
    )
    definitions.items[definition.id] = definition
    patient_boundary = FakeEventPatientBoundary()
    patient_boundary.register(corporate_id=corporate_id, patient_id=patient_id)
    store_operations = FakeMedicationHistoryStoreOperations()
    clock = FakeClock()
    create_event = CreateEventUseCase(
        event_repository=event_repository,
        event_definition_repository=definitions,
        patient_boundary=patient_boundary,
        corporate_access=access,
        store_operations=store_operations,
        clock=clock,
    )
    list_related_candidates = ListRelatedEventCandidatesUseCase(
        event_repository=event_repository,
        patient_boundary=patient_boundary,
        corporate_access=access,
        store_operations=store_operations,
    )
    return EventFixture(
        create_event=create_event,
        list_related_candidates=list_related_candidates,
        event_repository=event_repository,
        event_definition_repository=definitions,
        patient_boundary=patient_boundary,
        store_operations=store_operations,
        clock=clock,
        corporate_access=access,
        corporate_id=corporate_id,
        store_id=store_id,
        patient_id=patient_id,
        event_type_id=event_type_id,
    )


def create_command(
    fixture: EventFixture,
    *,
    occurred_at: datetime = datetime(2026, 8, 1, 3, 0, tzinfo=UTC),
    related_event_id: str | None = None,
    patient_id: PatientId | None = None,
    corporate_id: CorporateId | None = None,
    store_id: StoreId | None = None,
) -> CreateEventCommand:
    return CreateEventCommand(
        corporate_id=str((corporate_id or fixture.corporate_id).value),
        store_id=str((store_id or fixture.store_id).value),
        patient_id=str((patient_id or fixture.patient_id).value),
        event_type_id=str(fixture.event_type_id.value),
        occurred_at=occurred_at,
        related_event_id=related_event_id,
    )
