"""Applicationのupdate_event_definitionを定義する。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control.boundary_models import Permission
from app.application.access_control.errors import TenantBoundaryNotFoundError
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.care_event.commands.dtos.event_definition import EventDefinitionDto
from app.application.care_event.commands.services.event_definition import (
    ensure_event_definition_name_available,
)
from app.domain.care_event.identifiers import EventTypeId
from app.domain.care_event.primitives import EventTypeName
from app.domain.care_event.repositories import EventDefinitionRepository
from app.domain.corporate.identifiers import CorporateId
from app.domain.foundation.exceptions import DomainError


@dataclass(frozen=True, kw_only=True)
class UpdateEventDefinitionCommand:
    """法人独自イベント種別の改名・無効化入力。"""

    corporate_id: str
    event_type_id: str
    name: str | None = None
    is_active: bool | None = None


class UpdateEventDefinitionUseCase:
    """法人独自イベント種別を変更する。"""

    def __init__(
        self,
        repository: EventDefinitionRepository,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access

    async def execute(
        self, command: UpdateEventDefinitionCommand
    ) -> EventDefinitionDto:
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.MANAGE_EVENT_DEFINITION
        )
        definition_id = EventTypeId.parse(command.event_type_id)
        definition = await self._repository.get(
            corporate_id=corporate_id, event_type_id=definition_id
        )
        if definition is None or definition.corporate_id != corporate_id:
            raise TenantBoundaryNotFoundError()
        if command.name is None and command.is_active is None:
            raise DomainError("変更するイベント種別の項目を指定してください。")
        if command.name is not None:
            new_name = EventTypeName(command.name)
            others = tuple(
                item
                for item in await self._repository.list_for_corporate(
                    corporate_id=corporate_id
                )
                if item.id != definition.id
            )
            ensure_event_definition_name_available(others, new_name)
            definition = definition.rename(new_name)
        if command.is_active is False:
            definition = definition.deactivate()
        elif command.is_active is True and (not definition.is_active):
            raise DomainError("無効化したイベント種別は再有効化できません。")
        await self._repository.save(definition)
        return EventDefinitionDto.from_entity(definition)
