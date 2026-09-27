"""業務Event Repositoryのインメモリ実装。"""

from __future__ import annotations

import copy

from app.domain.care_event.event import Event
from app.domain.care_event.primitives import EventId
from app.domain.care_event.repository import (
    EventRepository,
    RelatedEventReference,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientId
from app.domain.reception.primitives import ReceptionId
from app.domain.store.primitives import StoreId


class InMemoryEventRepository(EventRepository):
    """Eventの法人・患者境界を反映するテスト用Repository。"""

    def __init__(self) -> None:
        self.items: dict[EventId, Event] = {}
        self.related_candidate_list_calls: list[tuple[CorporateId, PatientId]] = []

    async def get(
        self, *, corporate_id: CorporateId, event_id: EventId
    ) -> Event | None:
        event = self.items.get(event_id)
        if event is None or event.corporate_id != corporate_id:
            return None
        return copy.deepcopy(event)

    async def get_related(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
        event_id: EventId,
    ) -> Event | None:
        event = await self.get(corporate_id=corporate_id, event_id=event_id)
        if event is None or event.patient_id != patient_id:
            return None
        return event

    async def get_by_reception(
        self,
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
        reception_id: ReceptionId,
    ) -> Event | None:
        for event in self.items.values():
            if (
                event.corporate_id == corporate_id
                and event.store_id == store_id
                and event.reception_id == reception_id
            ):
                return copy.deepcopy(event)
        return None

    async def list_related_candidates(
        self, *, corporate_id: CorporateId, patient_id: PatientId
    ) -> tuple[RelatedEventReference, ...]:
        """同一法人・患者のEventについて候補に必要な値だけを返す。"""
        self.related_candidate_list_calls.append((corporate_id, patient_id))
        events = sorted(
            (
                event
                for event in self.items.values()
                if event.corporate_id == corporate_id and event.patient_id == patient_id
            ),
            key=lambda event: (event.created_at.value, event.id.value),
            reverse=True,
        )
        return tuple(
            RelatedEventReference(
                id=event.id,
                store_id=event.store_id,
                event_type_name=event.event_type_name,
                occurred_at=event.occurred_at,
                created_at=event.created_at,
            )
            for event in events
        )

    async def save(self, event: Event) -> None:
        self.items[event.id] = copy.deepcopy(event)
