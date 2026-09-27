"""患者の業務Eventを永続化するPostgreSQL Repository。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from sqlalchemy import select

from app.domain.care_event.event import Event
from app.domain.care_event.exceptions import EventAlreadyAssociatedError
from app.domain.care_event.primitives import (
    EventCreatedTimestamp,
    EventId,
    EventOccurredTimestamp,
    EventTypeName,
)
from app.domain.care_event.repository import EventRepository, RelatedEventReference
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientId
from app.domain.reception.primitives import ReceptionId
from app.domain.store.primitives import StoreId
from app.infrastructure.postgres.repository_base import (
    AggregateMapping,
    PostgresRepositoryBase,
)
from app.infrastructure.postgres.schema import care_events


def _event_columns(event: Event) -> dict[str, object]:
    """Eventの検索列を集約から導く。"""
    return {
        "id": event.id.value,
        "event_type_id": event.event_type_id.value,
        "event_definition_corporate_id": (
            event.event_definition_corporate_id.value
            if event.event_definition_corporate_id is not None
            else None
        ),
        "event_type_standard_code": (
            event.event_type_standard_code.value
            if event.event_type_standard_code is not None
            else None
        ),
        "event_type_name": event.event_type_name.value,
        "corporate_id": event.corporate_id.value,
        "store_id": event.store_id.value,
        "patient_id": event.patient_id.value,
        "occurred_at": (
            event.occurred_at.value if event.occurred_at is not None else None
        ),
        "occurred_at_is_unknown": event.occurred_at_is_unknown,
        "created_at": event.created_at.value,
        "related_event_id": (
            event.related_event_id.value if event.related_event_id is not None else None
        ),
        "reception_id": (
            event.reception_id.value if event.reception_id is not None else None
        ),
        "prescription_id": (
            event.prescription_id.value if event.prescription_id is not None else None
        ),
        "dispensing_id": (
            event.dispensing_id.value if event.dispensing_id is not None else None
        ),
    }


EVENT_MAPPING = AggregateMapping(
    table=care_events,
    aggregate_type=Event,
    label="業務Event",
    search_columns=_event_columns,
)


class PostgresEventRepository(PostgresRepositoryBase, EventRepository):
    """Eventの法人・店舗読取範囲と関連候補を扱う。"""

    async def get(
        self, *, corporate_id: CorporateId, event_id: EventId
    ) -> Event | None:
        return await self.get_by_id(EVENT_MAPPING, event_id, corporate_id=corporate_id)

    async def get_related(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
        event_id: EventId,
    ) -> Event | None:
        """同一法人・患者のEvent関連元を店舗横断で確認する。"""
        result = await self.session.execute(
            select(care_events).where(
                care_events.c.id == event_id.value,
                care_events.c.corporate_id == corporate_id.value,
                care_events.c.patient_id == patient_id.value,
            ),
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None
        return self._restore(EVENT_MAPPING, cast(Mapping[str, object], row))

    async def get_by_reception(
        self,
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
        reception_id: ReceptionId,
    ) -> Event | None:
        """受付に関連付くEventを、法人・店舗範囲で取得する。"""
        return await self.find_one(
            EVENT_MAPPING,
            select(care_events).where(
                care_events.c.corporate_id == corporate_id.value,
                care_events.c.store_id == store_id.value,
                care_events.c.reception_id == reception_id.value,
            ),
        )

    async def list_related_candidates(
        self, *, corporate_id: CorporateId, patient_id: PatientId
    ) -> tuple[RelatedEventReference, ...]:
        """本文やpayloadを取得せず、同一患者の店舗横断候補メタデータを返す。"""
        statement = (
            select(
                care_events.c.id,
                care_events.c.store_id,
                care_events.c.event_type_name,
                care_events.c.occurred_at,
                care_events.c.occurred_at_is_unknown,
                care_events.c.created_at,
            )
            .where(
                care_events.c.corporate_id == corporate_id.value,
                care_events.c.patient_id == patient_id.value,
            )
            .order_by(
                care_events.c.created_at.desc(),
                care_events.c.id.desc(),
            )
        )
        result = await self.session.execute(statement)
        return tuple(
            RelatedEventReference(
                id=EventId(row["id"]),
                store_id=StoreId(row["store_id"]),
                event_type_name=EventTypeName(row["event_type_name"]),
                occurred_at=(
                    EventOccurredTimestamp(row["occurred_at"])
                    if row["occurred_at"] is not None
                    else None
                ),
                created_at=EventCreatedTimestamp(row["created_at"]),
            )
            for row in result.mappings().all()
        )

    async def save(self, event: Event) -> None:
        await self.save_with_conflict_map(
            EVENT_MAPPING,
            event,
            conflicts={
                "uq_care_events_reception": EventAlreadyAssociatedError,
            },
        )
