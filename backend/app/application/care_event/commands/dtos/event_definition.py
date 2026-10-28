"""Applicationのevent_definitionを定義する。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.common.optional_conversion import unwrap
from app.domain.care_event.entities import EventDefinition


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
            corporate_id=str(definition.corporate_id.value)
            if definition.corporate_id is not None
            else None,
            name=definition.name.value,
            standard_code=unwrap(definition.standard_code),
            is_active=definition.is_active,
        )
