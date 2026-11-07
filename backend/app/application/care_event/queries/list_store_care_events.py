"""店舗の業務Event一覧を取得するユースケース。"""

from __future__ import annotations

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.access_control.interfaces.store_operations import (
    StoreOperation,
    StoreOperationBoundary,
)
from app.application.care_event.interfaces.list_store_care_events_query_reader import (
    ListStoreCareEventsQueryReader,
)
from app.application.care_event.queries.dtos.create_event import EventDto
from app.application.care_event.queries.models import ListStoreCareEventsQuery
from app.domain.corporate.identifiers import CorporateId
from app.domain.store.identifiers import StoreId


class ListStoreCareEventsUseCase:
    """店舗の業務Event一覧を取得する。"""

    def __init__(
        self,
        *,
        reader: ListStoreCareEventsQueryReader,
        corporate_access: CorporateAccessBoundary,
        store_operations: StoreOperationBoundary,
    ) -> None:
        self._reader = reader
        self._corporate_access = corporate_access
        self._store_operations = store_operations

    async def execute(self, query: ListStoreCareEventsQuery) -> tuple[EventDto, ...]:
        corporate_id = CorporateId.parse(query.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.VIEW_EVENT
        )
        store_id = StoreId.parse(query.store_id)
        await self._store_operations.require_allowed(
            corporate_id=corporate_id,
            store_id=store_id,
            operation=StoreOperation.READ_HISTORY,
        )
        return await self._reader.read(query)


__all__ = [
    "ListStoreCareEventsUseCase",
]
