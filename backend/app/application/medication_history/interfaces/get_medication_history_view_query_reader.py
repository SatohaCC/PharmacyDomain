"""Applicationのget_medication_history_view_query_readerを定義する。"""

from __future__ import annotations

from typing import Protocol

from app.application.medication_history.queries.dtos.get_medication_history_view import (
    MedicationHistoryViewDto,
)
from app.application.medication_history.queries.models import (
    GetMedicationHistoryViewQuery,
)


class GetMedicationHistoryViewQueryReader(Protocol):
    async def read(
        self, query: GetMedicationHistoryViewQuery
    ) -> MedicationHistoryViewDto:
        """認可済みの検索条件から、不変な参照結果だけを返す。"""
        ...
