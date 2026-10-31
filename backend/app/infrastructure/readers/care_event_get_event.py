"""Repositoryから参照用DTOを投影するアダプタ。保存は行わない。"""

from __future__ import annotations

from dataclasses import replace

from app.application.access_control.errors import TenantBoundaryNotFoundError
from app.application.care_event.interfaces.get_event_query_reader import (
    GetEventQueryReader,
)
from app.application.care_event.queries.dtos.create_event import EventDto
from app.application.care_event.queries.models import GetEventQuery
from app.domain.care_event.identifiers import EventId
from app.domain.care_event.repositories import EventRepository
from app.domain.corporate.identifiers import CorporateId


class GetEventProjection(GetEventQueryReader):
    """権限と店舗読取範囲を通してEventメタデータを取得する。"""

    def __init__(self, event_repository: EventRepository) -> None:
        self._event_repository = event_repository

    async def read(self, query: GetEventQuery) -> EventDto:
        corporate_id = CorporateId.parse(query.corporate_id)
        event = await self._event_repository.get(
            corporate_id=corporate_id, event_id=EventId.parse(query.event_id)
        )
        if event is None:
            raise TenantBoundaryNotFoundError()
        dto = EventDto.from_entity(event)
        if event.related_event_id is not None:
            related = await self._event_repository.get(
                corporate_id=corporate_id, event_id=event.related_event_id
            )
            if related is None or related.store_id != event.store_id:
                dto = replace(dto, related_event_id=None)
        return dto
