"""Applicationのget_store_opening_status_query_readerを定義する。"""

from __future__ import annotations

from typing import Protocol

from app.application.store.queries.dtos.business_hours import StoreOpeningStatusDto
from app.application.store.queries.models import StoreOpeningStatusQuery


class GetStoreOpeningStatusQueryReader(Protocol):
    async def read(self, query: StoreOpeningStatusQuery) -> StoreOpeningStatusDto:
        """認可済みの検索条件から、不変な参照結果だけを返す。"""
        ...
