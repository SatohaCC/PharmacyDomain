"""業務Eventのユースケース束。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.care_event.create_event import CreateEventUseCase
from app.application.care_event.event_definition import (
    CreateEventDefinitionUseCase,
    ListEventDefinitionsUseCase,
    UpdateEventDefinitionUseCase,
)
from app.application.care_event.get_event import GetEventUseCase
from app.application.care_event.list_related_candidates import (
    ListRelatedEventCandidatesUseCase,
)
from app.application.common.clock import Clock
from app.application.composition.care_event_references import (
    EventMedicationHistoryReferenceAdapter,
    EventPatientReferenceAdapter,
    EventReceptionReferenceAdapter,
)
from app.application.composition.store_operation_adapter import StoreOperationAdapter
from app.application.corporate.corporate_access import CorporateAccessService
from app.infrastructure.postgres.repositories.repository_set import (
    PostgresRepositorySet,
)


@dataclass(frozen=True, slots=True)
class CareEventUseCases:
    """業務Eventコンテキストの操作一式。"""

    create: CreateEventUseCase
    get: GetEventUseCase
    create_definition: CreateEventDefinitionUseCase
    list_definitions: ListEventDefinitionsUseCase
    update_definition: UpdateEventDefinitionUseCase
    list_related_candidates: ListRelatedEventCandidatesUseCase


def build_care_event_use_cases(
    repositories: PostgresRepositorySet,
    corporate_access: CorporateAccessService,
    clock: Clock,
) -> CareEventUseCases:
    """業務Eventのユースケースを同じRequestScopeのRepositoryへ接続する。"""
    store_operations = StoreOperationAdapter(
        repositories.store,
        corporate_access,
        repositories.manager_assignment,
        clock,
    )
    event_patient = EventPatientReferenceAdapter(repositories.patient)
    event_medication_history = EventMedicationHistoryReferenceAdapter(
        repositories.medication_history
    )
    return CareEventUseCases(
        create=CreateEventUseCase(
            event_repository=repositories.event,
            event_definition_repository=repositories.event_definition,
            patient_boundary=event_patient,
            corporate_access=corporate_access,
            store_operations=store_operations,
            clock=clock,
            reception_boundary=EventReceptionReferenceAdapter(repositories.reception),
            medication_history=event_medication_history,
        ),
        get=GetEventUseCase(
            event_repository=repositories.event,
            medication_history=event_medication_history,
            corporate_access=corporate_access,
            store_operations=store_operations,
        ),
        create_definition=CreateEventDefinitionUseCase(
            repositories.event_definition,
            corporate_access,
        ),
        list_definitions=ListEventDefinitionsUseCase(
            repositories.event_definition,
            corporate_access,
        ),
        update_definition=UpdateEventDefinitionUseCase(
            repositories.event_definition,
            corporate_access,
        ),
        list_related_candidates=ListRelatedEventCandidatesUseCase(
            event_repository=repositories.event,
            patient_boundary=event_patient,
            corporate_access=corporate_access,
            store_operations=store_operations,
        ),
    )


__all__ = ["CareEventUseCases", "build_care_event_use_cases"]
