"""Repositoryから参照用DTOを投影するアダプタ。保存は行わない。"""

from __future__ import annotations

from app.application.common.clock import Clock, business_date
from app.application.store.interfaces.list_stores_query_reader import (
    ListStoresQueryReader,
)
from app.application.store.queries.dtos.list_stores import StoreSummaryDto
from app.application.store.queries.models import ListStoresQuery
from app.domain.corporate.identifiers import CorporateId
from app.domain.store.repositories import StoreCatalogRepository


class ListStoresProjection(ListStoresQueryReader):
    """認可済みの対象法人に所属する店舗一覧を取得するユースケース。"""

    def __init__(
        self, repository: StoreCatalogRepository, clock: Clock | None = None
    ) -> None:
        self._repository = repository
        self._clock = clock

    async def read(self, query: ListStoresQuery) -> list[StoreSummaryDto]:
        corporate_id = CorporateId.parse(query.corporate_id)
        stores = await self._repository.list_by_corporate_id(corporate_id)
        as_of = business_date(self._clock) if self._clock is not None else None
        return [StoreSummaryDto.from_entity(store, as_of=as_of) for store in stores]
