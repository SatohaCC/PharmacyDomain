"""Applicationのget_store_query_readerを定義する。"""

from __future__ import annotations

from typing import Protocol

from app.application.store.queries.dtos.get_store import StoreDto
from app.application.store.queries.models import GetStoreQuery


class GetStoreQueryReader(Protocol):
    async def read(self, query: GetStoreQuery) -> StoreDto:
        """認可済みの検索条件から、不変な参照結果だけを返す。"""
        ...
