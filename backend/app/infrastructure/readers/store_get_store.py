"""Repositoryから参照用DTOを投影するアダプタ。保存は行わない。"""

from __future__ import annotations

from app.application.store.interfaces.get_store_query_reader import GetStoreQueryReader
from app.application.store.queries.dtos.get_store import StoreDto
from app.application.store.queries.models import GetStoreQuery
from app.domain.corporate.identifiers import CorporateId
from app.domain.store.identifiers import StoreId
from app.domain.store.repositories import StoreRepository
from app.infrastructure.readers.helpers.store_support import load_store_or_raise


class GetStoreProjection(GetStoreQueryReader):
    """店舗詳細取得ユースケース"""

    def __init__(self, repository: StoreRepository) -> None:
        self._repository = repository

    async def read(self, query: GetStoreQuery) -> StoreDto:
        corporate_id = CorporateId.parse(query.corporate_id)
        store_id = StoreId.parse(query.store_id)
        store = await load_store_or_raise(
            self._repository, corporate_id=corporate_id, store_id=store_id
        )
        return StoreDto.from_entity(store)
