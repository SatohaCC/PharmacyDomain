"""Applicationのlist_pending_external_corrections_query_readerを定義する。"""

from __future__ import annotations

from typing import Protocol

from app.application.common.pagination import Page
from app.application.medication_history.queries.dtos.list_pending_external_corrections import (
    PendingExternalCorrectionDto,
)
from app.application.medication_history.queries.models import (
    ListPendingExternalCorrectionsQuery,
)


class ListPendingExternalCorrectionsQueryReader(Protocol):
    async def read(
        self, query: ListPendingExternalCorrectionsQuery
    ) -> Page[PendingExternalCorrectionDto]:
        """認可済みの検索条件から、不変な参照結果だけを返す。"""
        ...
