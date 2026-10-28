"""Applicationのget_last_coverage_selection_query_readerを定義する。"""

from __future__ import annotations

from typing import Protocol

from app.application.coverage.queries.dtos.get_last_coverage_selection import (
    LastCoverageSelectionCandidateDto,
)
from app.application.coverage.queries.models import GetLastCoverageSelectionQuery


class GetLastCoverageSelectionQueryReader(Protocol):
    async def read(
        self, query: GetLastCoverageSelectionQuery
    ) -> LastCoverageSelectionCandidateDto | None:
        """認可済みの検索条件から、不変な参照結果だけを返す。"""
        ...
