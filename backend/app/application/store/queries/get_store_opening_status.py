"""Applicationのget_store_opening_statusを定義する。"""

from __future__ import annotations

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.store.interfaces.get_store_opening_status_query_reader import (
    GetStoreOpeningStatusQueryReader,
)
from app.application.store.queries.dtos.business_hours import StoreOpeningStatusDto
from app.application.store.queries.models import StoreOpeningStatusQuery
from app.domain.corporate.identifiers import CorporateId


class GetStoreOpeningStatusUseCase:
    def __init__(
        self,
        reader: GetStoreOpeningStatusQueryReader,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._reader = reader
        self._corporate_access = corporate_access

    async def execute(self, query: StoreOpeningStatusQuery) -> StoreOpeningStatusDto:
        """業務のタイムゾーンへ揃えてから判定する。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.VIEW_STORE
        )
        return await self._reader.read(query)
