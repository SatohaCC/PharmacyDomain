"""Applicationのlist_stores_query_readerを定義する。"""

from __future__ import annotations

from typing import Protocol

from app.application.store.queries.dtos.list_stores import StoreSummaryDto
from app.application.store.queries.models import ListStoresQuery


class ListStoresQueryReader(Protocol):
    async def read(self, query: ListStoresQuery) -> list[StoreSummaryDto]:
        """認可済みの検索条件から、不変な参照結果だけを返す。"""
        ...
