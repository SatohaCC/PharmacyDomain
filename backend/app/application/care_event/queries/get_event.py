"""Applicationのget_eventを定義する。"""

from __future__ import annotations

from dataclasses import replace

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.access_control.interfaces.store_operations import (
    StoreOperation,
    StoreOperationBoundary,
)
from app.application.care_event.interfaces.get_event_query_reader import (
    GetEventQueryReader,
)
from app.application.care_event.interfaces.references import (
    EventMedicationHistoryBoundary,
)
from app.application.care_event.queries.dtos.create_event import EventDto
from app.application.care_event.queries.models import GetEventQuery
from app.domain.care_event.identifiers import EventId
from app.domain.corporate.identifiers import CorporateId
from app.domain.store.identifiers import StoreId


class GetEventUseCase:
    def __init__(
        self,
        reader: GetEventQueryReader,
        medication_history: EventMedicationHistoryBoundary,
        corporate_access: CorporateAccessBoundary,
        store_operations: StoreOperationBoundary,
    ) -> None:
        self._reader = reader
        self._medication_history = medication_history
        self._corporate_access = corporate_access
        self._store_operations = store_operations

    async def execute(self, query: GetEventQuery) -> EventDto:
        corporate_id = CorporateId.parse(query.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.VIEW_EVENT
        )
        event = await self._reader.read(query)
        await self._store_operations.require_allowed(
            corporate_id=corporate_id,
            store_id=StoreId.parse(event.store_id),
            operation=StoreOperation.READ_HISTORY,
        )
        medication_history_id = await self._medication_history.get_id(
            corporate_id=corporate_id, event_id=EventId.parse(event.event_id)
        )
        return replace(event, medication_history_id=medication_history_id)
