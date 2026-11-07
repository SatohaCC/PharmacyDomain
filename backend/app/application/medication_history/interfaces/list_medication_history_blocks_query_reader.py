"""薬歴ブロック一覧のQueryReader契約。"""

from __future__ import annotations

from typing import Protocol

from app.application.medication_history.queries.dtos.medication_history_block import (
    MedicationHistoryBlockDto,
)
from app.application.medication_history.queries.models import (
    ListMedicationHistoryBlocksQuery,
)


class ListMedicationHistoryBlocksQueryReader(Protocol):
    """認可済みの薬歴ブロック一覧を返す契約。"""

    async def read(
        self, query: ListMedicationHistoryBlocksQuery
    ) -> tuple[MedicationHistoryBlockDto, ...]: ...


__all__ = ["ListMedicationHistoryBlocksQueryReader"]
