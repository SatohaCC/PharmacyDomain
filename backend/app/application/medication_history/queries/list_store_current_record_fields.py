"""店舗の今回記載欄設定一覧を取得するクエリユースケース。"""

from __future__ import annotations

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.access_control.interfaces.store_operations import (
    StoreOperation,
    StoreOperationBoundary,
)
from app.application.medication_history.interfaces.list_store_current_record_fields_query_reader import (
    ListStoreCurrentRecordFieldsQueryReader,
)
from app.application.medication_history.queries.dtos.category_catalog import (
    CurrentRecordFieldDto,
)
from app.application.medication_history.queries.models import (
    ListStoreCurrentRecordFieldsQuery,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.store.identifiers import StoreId


class ListStoreCurrentRecordFieldsUseCase:
    """店舗の今回記載欄設定一覧を取得する。"""

    def __init__(
        self,
        *,
        reader: ListStoreCurrentRecordFieldsQueryReader,
        corporate_access: CorporateAccessBoundary,
        store_operations: StoreOperationBoundary,
    ) -> None:
        self._reader = reader
        self._corporate_access = corporate_access
        self._store_operations = store_operations

    async def execute(
        self, query: ListStoreCurrentRecordFieldsQuery
    ) -> tuple[CurrentRecordFieldDto, ...]:
        """店舗に適用される今回記載欄項目を取得する。"""
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
    "ListStoreCurrentRecordFieldsQuery",
    "ListStoreCurrentRecordFieldsUseCase",
]
