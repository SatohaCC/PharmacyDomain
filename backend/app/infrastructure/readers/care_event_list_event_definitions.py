"""Repositoryから参照用DTOを投影するアダプタ。保存は行わない。"""

from __future__ import annotations

from app.application.care_event.interfaces.list_event_definitions_query_reader import (
    ListEventDefinitionsQueryReader,
)
from app.application.care_event.queries.dtos.event_definition import EventDefinitionDto
from app.domain.care_event.repositories import EventDefinitionRepository
from app.domain.corporate.identifiers import CorporateId


class ListEventDefinitionsProjection(ListEventDefinitionsQueryReader):
    """標準と指定法人のイベント種別を一覧する。"""

    def __init__(self, repository: EventDefinitionRepository) -> None:
        self._repository = repository

    async def read(self, corporate_id: str) -> tuple[EventDefinitionDto, ...]:
        parsed_corporate_id = CorporateId.parse(corporate_id)
        definitions = await self._repository.list_for_corporate(
            corporate_id=parsed_corporate_id
        )
        return tuple(EventDefinitionDto.from_entity(item) for item in definitions)
