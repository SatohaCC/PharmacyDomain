"""業務Eventのユースケース束。"""

from __future__ import annotations

from app.application.care_event.commands.create_event import CreateEventUseCase
from app.application.care_event.commands.create_event_definition import (
    CreateEventDefinitionUseCase,
)
from app.application.care_event.commands.update_event_definition import (
    UpdateEventDefinitionUseCase,
)
from app.application.care_event.queries.get_event import GetEventUseCase
from app.application.care_event.queries.list_event_definitions import (
    ListEventDefinitionsUseCase,
)
from app.application.care_event.queries.list_related_event_candidates import (
    ListRelatedEventCandidatesUseCase,
)
from app.application.common.clock import Clock
from app.application.composition.adapters.care_event_references import (
    EventMedicationHistoryReferenceAdapter,
    EventPatientReferenceAdapter,
    EventReceptionReferenceAdapter,
)
from app.application.composition.adapters.store_operation_adapter import (
    StoreOperationAdapter,
)
from app.application.composition.registry import CareEventUseCases
from app.application.corporate.commands.services.corporate_access import (
    CorporateAccessService,
)
from app.infrastructure.di.repositories import (
    PostgresRepositorySet,
)
from app.infrastructure.readers.care_event_get_event import GetEventProjection
from app.infrastructure.readers.care_event_list_event_definitions import (
    ListEventDefinitionsProjection,
)
from app.infrastructure.readers.care_event_list_related_event_candidates import (
    ListRelatedEventCandidatesProjection,
)


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
            reader=GetEventProjection(event_repository=repositories.event),
            medication_history=event_medication_history,
            corporate_access=corporate_access,
            store_operations=store_operations,
        ),
        create_definition=CreateEventDefinitionUseCase(
            repositories.event_definition,
            corporate_access,
        ),
        list_definitions=ListEventDefinitionsUseCase(
            reader=ListEventDefinitionsProjection(repositories.event_definition),
            corporate_access=corporate_access,
        ),
        update_definition=UpdateEventDefinitionUseCase(
            repositories.event_definition,
            corporate_access,
        ),
        list_related_candidates=ListRelatedEventCandidatesUseCase(
            reader=ListRelatedEventCandidatesProjection(
                event_repository=repositories.event
            ),
            patient_boundary=event_patient,
            corporate_access=corporate_access,
            store_operations=store_operations,
        ),
    )


__all__ = ["CareEventUseCases", "build_care_event_use_cases"]
