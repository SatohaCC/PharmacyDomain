"""Applicationのget_follow_up_source_query_readerを定義する。"""

from __future__ import annotations

from typing import Protocol

from app.application.medication_history.queries.dtos.get_medication_history import (
    FollowUpSourceDto,
)
from app.application.medication_history.queries.models import GetFollowUpSourceQuery


class GetFollowUpSourceQueryReader(Protocol):
    async def read(self, query: GetFollowUpSourceQuery) -> FollowUpSourceDto:
        """認可済みの検索条件から、不変な参照結果だけを返す。"""
        ...
