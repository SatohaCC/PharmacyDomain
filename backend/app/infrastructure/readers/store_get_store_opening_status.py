"""Repositoryから参照用DTOを投影するアダプタ。保存は行わない。"""

from __future__ import annotations

from app.application.common.clock import Clock
from app.application.store.interfaces.get_store_opening_status_query_reader import (
    GetStoreOpeningStatusQueryReader,
)
from app.application.store.queries.dtos.business_hours import StoreOpeningStatusDto
from app.application.store.queries.models import StoreOpeningStatusQuery
from app.application.store.queries.services.business_hours import (
    _business_moment,
    _status_of,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.store.identifiers import StoreId
from app.domain.store.repositories import StoreRepository
from app.infrastructure.readers.helpers.store_support import load_store_or_raise


class GetStoreOpeningStatusProjection(GetStoreOpeningStatusQueryReader):
    """指定日時に店舗が開いているかを返す。"""

    def __init__(self, repository: StoreRepository, clock: Clock) -> None:
        self._repository = repository
        self._clock = clock

    async def read(self, query: StoreOpeningStatusQuery) -> StoreOpeningStatusDto:
        """業務のタイムゾーンへ揃えてから判定する。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        store = await load_store_or_raise(
            self._repository,
            corporate_id=corporate_id,
            store_id=StoreId.parse(query.store_id),
        )
        return _status_of(store, _business_moment(query.at, self._clock))
