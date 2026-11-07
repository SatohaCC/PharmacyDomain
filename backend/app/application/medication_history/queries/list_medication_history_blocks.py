"""薬歴ブロック一覧を取得するクエリユースケース。"""

from __future__ import annotations

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.access_control.interfaces.store_operations import (
    StoreOperation,
    StoreOperationBoundary,
)
from app.application.medication_history.interfaces.list_medication_history_blocks_query_reader import (
    ListMedicationHistoryBlocksQueryReader,
)
from app.application.medication_history.queries.dtos.medication_history_block import (
    MedicationHistoryBlockDto,
)
from app.application.medication_history.queries.models import (
    ListMedicationHistoryBlocksQuery,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.store.identifiers import StoreId


class ListMedicationHistoryBlocksUseCase:
    """薬歴ブロック一覧を取得する。"""

    def __init__(
        self,
        *,
        reader: ListMedicationHistoryBlocksQueryReader,
        corporate_access: CorporateAccessBoundary,
        store_operations: StoreOperationBoundary,
    ) -> None:
        self._reader = reader
        self._corporate_access = corporate_access
        self._store_operations = store_operations

    async def execute(
        self, query: ListMedicationHistoryBlocksQuery
    ) -> tuple[MedicationHistoryBlockDto, ...]:
        """薬歴ブロック一覧を取得する。"""
        parsed_corporate_id = CorporateId.parse(query.corporate_id)
        parsed_store_id = StoreId.parse(query.store_id)
        await self._corporate_access.require_active(
            corporate_id=parsed_corporate_id,
            permission=Permission.MANAGE_MEDICATION_HISTORY,
        )
        await self._store_operations.require_allowed(
            corporate_id=parsed_corporate_id,
            store_id=parsed_store_id,
            operation=StoreOperation.READ_HISTORY,
        )
        return await self._reader.read(query)


__all__ = [
    "ListMedicationHistoryBlocksQuery",
    "ListMedicationHistoryBlocksUseCase",
]
