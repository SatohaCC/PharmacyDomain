"""Applicationのlist_related_event_candidates_query_readerを定義する。"""

from __future__ import annotations

from typing import Protocol

from app.application.care_event.queries.dtos.list_related_candidates import (
    RelatedEventCandidateDto,
)
from app.application.care_event.queries.models import ListRelatedEventCandidatesQuery


class ListRelatedEventCandidatesQueryReader(Protocol):
    async def read(
        self, query: ListRelatedEventCandidatesQuery
    ) -> tuple[RelatedEventCandidateDto, ...]:
        """認可済みの検索条件から、不変な参照結果だけを返す。"""
        ...
