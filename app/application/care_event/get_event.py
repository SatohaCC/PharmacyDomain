"""業務Eventの参照ユースケース。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control.boundary import CorporateAccessBoundary
from app.application.access_control.exceptions import TenantBoundaryNotFoundError
from app.application.access_control.models import Permission
from app.application.access_control.store_access import (
    StoreOperation,
    StoreOperationBoundary,
)
from app.application.care_event.create_event import EventDto
from app.application.care_event.references import EventMedicationHistoryBoundary
from app.domain.care_event.primitives import EventId
from app.domain.care_event.repository import EventRepository
from app.domain.corporate.primitives import CorporateId


@dataclass(frozen=True, kw_only=True)
class GetEventQuery:
    """Event取得の入力。"""

    corporate_id: str
    event_id: str


class GetEventUseCase:
    """権限と店舗読取範囲を通してEventメタデータを取得する。"""

    def __init__(
        self,
        event_repository: EventRepository,
        medication_history: EventMedicationHistoryBoundary,
        corporate_access: CorporateAccessBoundary,
        store_operations: StoreOperationBoundary,
    ) -> None:
        self._event_repository = event_repository
        self._medication_history = medication_history
        self._corporate_access = corporate_access
        self._store_operations = store_operations

    async def execute(self, query: GetEventQuery) -> EventDto:
        corporate_id = CorporateId.parse(query.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.VIEW_EVENT,
        )
        event = await self._event_repository.get(
            corporate_id=corporate_id,
            event_id=EventId.parse(query.event_id),
        )
        if event is None:
            raise TenantBoundaryNotFoundError()
        await self._store_operations.require_allowed(
            corporate_id=corporate_id,
            store_id=event.store_id,
            operation=StoreOperation.READ_HISTORY,
        )
        medication_history_id = await self._medication_history.get_id(
            corporate_id=corporate_id,
            event_id=event.id,
        )
        return EventDto.from_entity(
            event,
            medication_history_id=medication_history_id,
        )
