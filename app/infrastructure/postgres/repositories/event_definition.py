"""業務Event種別定義のPostgreSQL Repository。"""

from __future__ import annotations

from sqlalchemy import select

from app.domain.care_event.event_definition import EventDefinition
from app.domain.care_event.exceptions import EventDefinitionAlreadyExistsError
from app.domain.care_event.primitives import EventTypeId
from app.domain.care_event.repository import EventDefinitionRepository
from app.domain.corporate.primitives import CorporateId
from app.infrastructure.postgres.repository_base import (
    AggregateMapping,
    PostgresRepositoryBase,
)
from app.infrastructure.postgres.schema import event_definitions


def _event_definition_columns(definition: EventDefinition) -> dict[str, object]:
    """種別定義の検索列を集約から導く。"""
    return {
        "id": definition.id.value,
        "corporate_id": (
            definition.corporate_id.value
            if definition.corporate_id is not None
            else None
        ),
        "standard_code": (
            definition.standard_code.value
            if definition.standard_code is not None
            else None
        ),
        "name": definition.name.value,
        "is_active": definition.is_active,
    }


EVENT_DEFINITION_MAPPING = AggregateMapping(
    table=event_definitions,
    aggregate_type=EventDefinition,
    label="イベント種別",
    search_columns=_event_definition_columns,
)


class PostgresEventDefinitionRepository(
    PostgresRepositoryBase, EventDefinitionRepository
):
    """標準および法人独自のイベント種別を永続化する。"""

    async def get(
        self, *, corporate_id: CorporateId, event_type_id: EventTypeId
    ) -> EventDefinition | None:
        return await self.find_one(
            EVENT_DEFINITION_MAPPING,
            select(event_definitions).where(
                event_definitions.c.id == event_type_id.value,
                (
                    event_definitions.c.corporate_id.is_(None)
                    | (event_definitions.c.corporate_id == corporate_id.value)
                ),
            ),
        )

    async def list_for_corporate(
        self, *, corporate_id: CorporateId
    ) -> tuple[EventDefinition, ...]:
        items = await self.find_all(
            EVENT_DEFINITION_MAPPING,
            select(event_definitions)
            .where(
                event_definitions.c.corporate_id.is_(None)
                | (event_definitions.c.corporate_id == corporate_id.value)
            )
            .order_by(
                event_definitions.c.corporate_id.nullsfirst(),
                event_definitions.c.name,
                event_definitions.c.id,
            ),
        )
        return tuple(items)

    async def save(self, definition: EventDefinition) -> None:
        await self.save_with_conflict_map(
            EVENT_DEFINITION_MAPPING,
            definition,
            conflicts={
                "uq_event_definitions_corporate_active_name": (
                    EventDefinitionAlreadyExistsError
                ),
                "uq_event_definitions_standard_code": (
                    EventDefinitionAlreadyExistsError
                ),
            },
        )
