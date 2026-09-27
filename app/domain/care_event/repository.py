"""業務Event集約のRepository Protocol。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.domain.care_event.event import Event
from app.domain.care_event.event_definition import EventDefinition
from app.domain.care_event.primitives import (
    EventCreatedTimestamp,
    EventId,
    EventOccurredTimestamp,
    EventTypeId,
    EventTypeName,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientId
from app.domain.reception.primitives import ReceptionId
from app.domain.store.primitives import StoreId


@dataclass(frozen=True, kw_only=True)
class RelatedEventReference:
    """関連Event選択で公開してよい本文を含まないメタデータ。"""

    id: EventId
    store_id: StoreId
    event_type_name: EventTypeName
    occurred_at: EventOccurredTimestamp | None
    created_at: EventCreatedTimestamp


class EventDefinitionRepository(Protocol):
    """標準および法人独自の種別定義を保存・検索する。"""

    async def get(
        self, *, corporate_id: CorporateId, event_type_id: EventTypeId
    ) -> EventDefinition | None: ...

    async def list_for_corporate(
        self, *, corporate_id: CorporateId
    ) -> tuple[EventDefinition, ...]: ...

    async def save(self, definition: EventDefinition) -> None: ...


class EventRepository(Protocol):
    """患者の業務Eventをテナント範囲内で保存・参照する。"""

    async def get(
        self, *, corporate_id: CorporateId, event_id: EventId
    ) -> Event | None: ...

    async def get_related(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
        event_id: EventId,
    ) -> Event | None: ...

    async def get_by_reception(
        self,
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
        reception_id: ReceptionId,
    ) -> Event | None:
        """受付に関連付くEventを法人・店舗境界内で取得する。"""
        ...

    async def list_related_candidates(
        self, *, corporate_id: CorporateId, patient_id: PatientId
    ) -> tuple[RelatedEventReference, ...]: ...

    async def save(self, event: Event) -> None: ...
