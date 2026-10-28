"""Repositoryから参照用DTOを投影するアダプタ。保存は行わない。"""

from __future__ import annotations

from app.application.care_event.interfaces.list_related_event_candidates_query_reader import (
    ListRelatedEventCandidatesQueryReader,
)
from app.application.care_event.queries.dtos.list_related_candidates import (
    RelatedEventCandidateDto,
)
from app.application.care_event.queries.models import ListRelatedEventCandidatesQuery
from app.domain.care_event.repositories import EventRepository
from app.domain.corporate.identifiers import CorporateId
from app.domain.patient.identifiers import PatientId
from app.domain.store.identifiers import StoreId


class ListRelatedEventCandidatesProjection(ListRelatedEventCandidatesQueryReader):
    """許可店舗で業務を開始したActorへ、同一患者Eventの候補を返す。"""

    def __init__(self, event_repository: EventRepository) -> None:
        self._event_repository = event_repository

    async def read(
        self, query: ListRelatedEventCandidatesQuery
    ) -> tuple[RelatedEventCandidateDto, ...]:
        corporate_id = CorporateId.parse(query.corporate_id)
        StoreId.parse(query.store_id)
        patient_id = PatientId.parse(query.patient_id)
        references = await self._event_repository.list_related_candidates(
            corporate_id=corporate_id, patient_id=patient_id
        )
        return tuple(
            RelatedEventCandidateDto(
                event_id=str(item.id.value),
                store_id=str(item.store_id.value),
                event_type_name=item.event_type_name.value,
                occurred_at=item.occurred_at.value.isoformat()
                if item.occurred_at is not None
                else None,
                occurred_at_is_unknown=item.occurred_at is None,
                created_at=item.created_at.value.isoformat(),
            )
            for item in references
        )
