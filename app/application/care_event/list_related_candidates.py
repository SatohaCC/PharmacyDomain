"""同一患者の関連Event候補を本文なしで返す。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control.boundary import CorporateAccessBoundary
from app.application.access_control.models import Permission
from app.application.access_control.store_access import (
    StoreOperation,
    StoreOperationBoundary,
)
from app.application.care_event.references import EventPatientBoundary
from app.domain.care_event.repository import EventRepository
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientId
from app.domain.store.primitives import StoreId


@dataclass(frozen=True, kw_only=True)
class RelatedEventCandidateDto:
    """関連Eventとして選べる最小限の情報。"""

    event_id: str
    store_id: str
    event_type_name: str
    occurred_at: str | None
    occurred_at_is_unknown: bool
    created_at: str


@dataclass(frozen=True, kw_only=True)
class ListRelatedEventCandidatesQuery:
    """関連候補一覧の入力。"""

    corporate_id: str
    store_id: str
    patient_id: str


class ListRelatedEventCandidatesUseCase:
    """許可店舗で業務を開始したActorへ、同一患者Eventの候補を返す。"""

    def __init__(
        self,
        event_repository: EventRepository,
        patient_boundary: EventPatientBoundary,
        corporate_access: CorporateAccessBoundary,
        store_operations: StoreOperationBoundary,
    ) -> None:
        self._event_repository = event_repository
        self._patient_boundary = patient_boundary
        self._corporate_access = corporate_access
        self._store_operations = store_operations

    async def execute(
        self, query: ListRelatedEventCandidatesQuery
    ) -> tuple[RelatedEventCandidateDto, ...]:
        corporate_id = CorporateId.parse(query.corporate_id)
        store_id = StoreId.parse(query.store_id)
        patient_id = PatientId.parse(query.patient_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.VIEW_EVENT,
        )
        await self._store_operations.require_allowed(
            corporate_id=corporate_id,
            store_id=store_id,
            operation=StoreOperation.READ_HISTORY,
        )
        await self._patient_boundary.require_exists(
            corporate_id=corporate_id,
            patient_id=patient_id,
        )
        references = await self._event_repository.list_related_candidates(
            corporate_id=corporate_id,
            patient_id=patient_id,
        )
        return tuple(
            RelatedEventCandidateDto(
                event_id=str(item.id.value),
                store_id=str(item.store_id.value),
                event_type_name=item.event_type_name.value,
                occurred_at=(
                    item.occurred_at.value.isoformat()
                    if item.occurred_at is not None
                    else None
                ),
                occurred_at_is_unknown=item.occurred_at is None,
                created_at=item.created_at.value.isoformat(),
            )
            for item in references
        )
