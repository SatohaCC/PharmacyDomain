"""イベント種別管理ユースケースの承認済み入口。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control.boundary import CorporateAccessBoundary
from app.application.access_control.exceptions import TenantBoundaryNotFoundError
from app.application.access_control.models import Permission
from app.application.common.optional_conversion import unwrap
from app.domain.care_event.event_definition import EventDefinition
from app.domain.care_event.primitives import EventTypeId, EventTypeName
from app.domain.care_event.repository import EventDefinitionRepository
from app.domain.corporate.primitives import CorporateId
from app.domain.foundation.exceptions import DomainError


@dataclass(frozen=True, kw_only=True)
class EventDefinitionDto:
    """イベント種別の外向けDTO。"""

    id: str
    corporate_id: str | None
    name: str
    standard_code: str | None
    is_active: bool

    @classmethod
    def from_entity(cls, definition: EventDefinition) -> EventDefinitionDto:
        """種別定義を公開DTOに変換する。"""
        return cls(
            id=str(definition.id.value),
            corporate_id=(
                str(definition.corporate_id.value)
                if definition.corporate_id is not None
                else None
            ),
            name=definition.name.value,
            standard_code=unwrap(definition.standard_code),
            is_active=definition.is_active,
        )


@dataclass(frozen=True, kw_only=True)
class CreateEventDefinitionCommand:
    """法人独自イベント種別の作成入力。"""

    corporate_id: str
    name: str


@dataclass(frozen=True, kw_only=True)
class UpdateEventDefinitionCommand:
    """法人独自イベント種別の改名・無効化入力。"""

    corporate_id: str
    event_type_id: str
    name: str | None = None
    is_active: bool | None = None


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
            corporate_id=corporate_id,
            permission=Permission.MANAGE_EVENT_DEFINITION,
        )
        name = EventTypeName(command.name)
        self._ensure_name_available(
            await self._repository.list_for_corporate(corporate_id=corporate_id),
            name,
        )
        definition = EventDefinition.create_custom(
            corporate_id=corporate_id,
            name=name,
        )
        await self._repository.save(definition)
        return EventDefinitionDto.from_entity(definition)

    @staticmethod
    def _ensure_name_available(
        definitions: tuple[EventDefinition, ...], name: EventTypeName
    ) -> None:
        if any(
            item.corporate_id is not None and item.is_active and item.name == name
            for item in definitions
        ):
            raise DomainError("法人内で有効な同名イベント種別があります。")


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
            corporate_id=corporate_id,
            permission=Permission.MANAGE_EVENT_DEFINITION,
        )
        definition_id = EventTypeId.parse(command.event_type_id)
        definition = await self._repository.get(
            corporate_id=corporate_id,
            event_type_id=definition_id,
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
            CreateEventDefinitionUseCase._ensure_name_available(others, new_name)
            definition = definition.rename(new_name)
        if command.is_active is False:
            definition = definition.deactivate()
        elif command.is_active is True and not definition.is_active:
            raise DomainError("無効化したイベント種別は再有効化できません。")
        await self._repository.save(definition)
        return EventDefinitionDto.from_entity(definition)


class ListEventDefinitionsUseCase:
    """標準と指定法人のイベント種別を一覧する。"""

    def __init__(
        self,
        repository: EventDefinitionRepository,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access

    async def execute(self, corporate_id: str) -> tuple[EventDefinitionDto, ...]:
        parsed_corporate_id = CorporateId.parse(corporate_id)
        await self._corporate_access.require_active(
            corporate_id=parsed_corporate_id,
            permission=Permission.VIEW_EVENT,
        )
        definitions = await self._repository.list_for_corporate(
            corporate_id=parsed_corporate_id
        )
        return tuple(EventDefinitionDto.from_entity(item) for item in definitions)
