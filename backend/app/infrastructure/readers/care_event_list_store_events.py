"""Repositoryから店舗の業務Event一覧を投影するアダプタ。"""

from __future__ import annotations

from app.application.care_event.interfaces.list_store_care_events_query_reader import (
    ListStoreCareEventsQueryReader,
)
from app.application.care_event.queries.dtos.create_event import EventDto
from app.application.care_event.queries.models import ListStoreCareEventsQuery
from app.domain.care_event.repositories import EventRepository
from app.domain.corporate.identifiers import CorporateId
from app.domain.patient.identifiers import PatientId
from app.domain.store.identifiers import StoreId


class ListStoreCareEventsProjection(ListStoreCareEventsQueryReader):
    """店舗の業務Event一覧をDTOへ変換して返す。"""

    def __init__(self, repository: EventRepository) -> None:
        self._repository = repository

    async def read(self, query: ListStoreCareEventsQuery) -> tuple[EventDto, ...]:
        corporate_id = CorporateId.parse(query.corporate_id)
        store_id = StoreId.parse(query.store_id)
        patient_id = (
            PatientId.parse(query.patient_id) if query.patient_id is not None else None
        )
        events = await self._repository.list_by_store(
            corporate_id=corporate_id,
            store_id=store_id,
            patient_id=patient_id,
        )
        return tuple(EventDto.from_entity(item) for item in events)
