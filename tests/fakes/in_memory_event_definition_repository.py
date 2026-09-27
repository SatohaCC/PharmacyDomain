"""業務イベント種別Repositoryのインメモリ実装。"""

from __future__ import annotations

import copy

from app.domain.care_event.event_definition import EventDefinition
from app.domain.care_event.primitives import EventTypeId
from app.domain.care_event.repository import EventDefinitionRepository
from app.domain.corporate.primitives import CorporateId


class InMemoryEventDefinitionRepository(EventDefinitionRepository):
    """標準および法人別の種別を保持するテスト用Repository。"""

    def __init__(self) -> None:
        self.items: dict[EventTypeId, EventDefinition] = {}

    async def get(
        self, *, corporate_id: CorporateId, event_type_id: EventTypeId
    ) -> EventDefinition | None:
        item = self.items.get(event_type_id)
        if item is None or item.corporate_id not in {None, corporate_id}:
            return None
        return copy.deepcopy(item)

    async def list_for_corporate(
        self, *, corporate_id: CorporateId
    ) -> tuple[EventDefinition, ...]:
        return tuple(
            copy.deepcopy(item)
            for item in self.items.values()
            if item.corporate_id in {None, corporate_id}
        )

    async def save(self, definition: EventDefinition) -> None:
        self.items[definition.id] = copy.deepcopy(definition)
