"""Applicationのget_event_query_readerを定義する。"""

from __future__ import annotations

from typing import Protocol

from app.application.care_event.queries.dtos.create_event import EventDto
from app.application.care_event.queries.models import GetEventQuery


class GetEventQueryReader(Protocol):
    async def read(self, query: GetEventQuery) -> EventDto:
        """認可済みの検索条件から、不変な参照結果だけを返す。"""
        ...
