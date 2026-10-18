"""care_eventの保存・情報取得の抽象契約。"""

from __future__ import annotations

from typing import Protocol

from app.domain.care_event.entities import Event, EventDefinition
from app.domain.care_event.identifiers import EventId, EventTypeId
from app.domain.care_event.value_objects import RelatedEventReference
from app.domain.corporate.identifiers import CorporateId
from app.domain.patient.identifiers import PatientId
from app.domain.reception.identifiers import ReceptionId
from app.domain.store.identifiers import StoreId


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
