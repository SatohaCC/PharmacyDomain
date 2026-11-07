"""Applicationのlist_store_care_events_query_readerを定義する。"""

from __future__ import annotations

from typing import Protocol

from app.application.care_event.queries.dtos.create_event import EventDto
from app.application.care_event.queries.models import ListStoreCareEventsQuery


class ListStoreCareEventsQueryReader(Protocol):
    async def read(self, query: ListStoreCareEventsQuery) -> tuple[EventDto, ...]:
        """認可済みの店舗Event一覧を返す。"""
        ...
