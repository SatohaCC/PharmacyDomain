"""Applicationのlist_event_definitionsを定義する。"""

from __future__ import annotations

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.care_event.interfaces.list_event_definitions_query_reader import (
    ListEventDefinitionsQueryReader,
)
from app.application.care_event.queries.dtos.event_definition import EventDefinitionDto
from app.domain.corporate.identifiers import CorporateId


class ListEventDefinitionsUseCase:
    def __init__(
        self,
        reader: ListEventDefinitionsQueryReader,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._reader = reader
        self._corporate_access = corporate_access

    async def execute(self, corporate_id: str) -> tuple[EventDefinitionDto, ...]:
        parsed_corporate_id = CorporateId.parse(corporate_id)
        await self._corporate_access.require_active(
            corporate_id=parsed_corporate_id, permission=Permission.VIEW_EVENT
        )
        return await self._reader.read(corporate_id)
