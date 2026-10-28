"""Applicationのlist_event_definitions_query_readerを定義する。"""

from __future__ import annotations

from typing import Protocol

from app.application.care_event.queries.dtos.event_definition import EventDefinitionDto


class ListEventDefinitionsQueryReader(Protocol):
    async def read(self, corporate_id: str) -> tuple[EventDefinitionDto, ...]:
        """認可済みの検索条件から、不変な参照結果だけを返す。"""
        ...
