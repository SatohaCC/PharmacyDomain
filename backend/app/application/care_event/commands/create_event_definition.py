"""Applicationのcreate_event_definitionを定義する。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.care_event.commands.dtos.event_definition import EventDefinitionDto
from app.application.care_event.commands.services.event_definition import (
    ensure_event_definition_name_available,
)
from app.domain.care_event.entities import EventDefinition
from app.domain.care_event.primitives import EventTypeName
from app.domain.care_event.repositories import EventDefinitionRepository
from app.domain.corporate.identifiers import CorporateId


@dataclass(frozen=True, kw_only=True)
class CreateEventDefinitionCommand:
    """法人独自イベント種別の作成入力。"""

    corporate_id: str
    name: str


class CreateEventDefinitionUseCase:
    """法人独自イベント種別を作成する。"""

    def __init__(
        self,
        repository: EventDefinitionRepository,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access

    async def execute(
        self, command: CreateEventDefinitionCommand
    ) -> EventDefinitionDto:
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.MANAGE_EVENT_DEFINITION
        )
        name = EventTypeName(command.name)
        ensure_event_definition_name_available(
            await self._repository.list_for_corporate(corporate_id=corporate_id), name
        )
        definition = EventDefinition.create_custom(corporate_id=corporate_id, name=name)
        await self._repository.save(definition)
        return EventDefinitionDto.from_entity(definition)
