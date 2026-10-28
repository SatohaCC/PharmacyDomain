"""Applicationのlist_corporates_query_readerを定義する。"""

from __future__ import annotations

from typing import Protocol

from app.application.corporate.queries.dtos.list_corporates import CorporatePageDto
from app.application.corporate.queries.models import ListCorporatesQuery


class ListCorporatesQueryReader(Protocol):
    async def read(self, query: ListCorporatesQuery) -> CorporatePageDto:
        """認可済みの検索条件から、不変な参照結果だけを返す。"""
        ...
