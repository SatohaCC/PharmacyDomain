"""受付に紐づく薬歴識別情報のQueryReader契約。"""

from __future__ import annotations

from typing import Protocol

from app.application.reception.queries.models import (
    ResolveReceptionMedicationHistoryQuery,
)


class ResolveReceptionMedicationHistoryQueryReader(Protocol):
    """認可済みの受付に紐づく薬歴IDまたはEvent IDを返す契約。"""

    async def read(
        self, query: ResolveReceptionMedicationHistoryQuery
    ) -> str | None: ...


__all__ = ["ResolveReceptionMedicationHistoryQueryReader"]
