"""Applicationのlist_storesを定義する。"""

from __future__ import annotations

from app.application.access_control.boundary_models import (
    ActorRole,
    Permission,
    ResolvedActorContext,
)
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.store.interfaces.list_stores_query_reader import (
    ListStoresQueryReader,
)
from app.application.store.queries.dtos.list_stores import StoreSummaryDto
from app.application.store.queries.models import ListStoresQuery
from app.domain.corporate.identifiers import CorporateId
from app.domain.store.identifiers import StoreId


class ListStoresUseCase:
    def __init__(
        self, reader: ListStoresQueryReader, corporate_access: CorporateAccessBoundary
    ) -> None:
        self._reader = reader
        self._corporate_access = corporate_access

    async def execute(self, query: ListStoresQuery) -> list[StoreSummaryDto]:
        corporate_id = CorporateId.parse(query.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.VIEW_STORE
        )
        stores = await self._reader.read(query)
        actor = self._corporate_access.actor
        if isinstance(actor, ResolvedActorContext) and (
            not actor.roles & {ActorRole.VENDOR_SYSTEM_ADMIN, ActorRole.CORPORATE_ADMIN}
        ):
            return [
                store for store in stores if StoreId.parse(store.id) in actor.store_ids
            ]
        return stores
