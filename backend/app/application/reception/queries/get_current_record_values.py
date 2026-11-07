"""受付の今回記載欄入力値を取得するユースケース。"""

from __future__ import annotations

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.reception.interfaces.get_current_record_values_query_reader import (
    GetCurrentRecordValuesQueryReader,
)
from app.application.reception.queries.dtos.current_record_values import (
    CurrentRecordFieldValueDto,
)
from app.application.reception.queries.models import GetCurrentRecordValuesQuery
from app.domain.corporate.identifiers import CorporateId


class GetCurrentRecordValuesUseCase:
    """受付の今回記載欄入力値を取得する。"""

    def __init__(
        self,
        *,
        reader: GetCurrentRecordValuesQueryReader,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._reader = reader
        self._corporate_access = corporate_access

    async def execute(
        self, query: GetCurrentRecordValuesQuery
    ) -> tuple[CurrentRecordFieldValueDto, ...]:
        """受付の今回記載欄入力値を取得する。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.VIEW_RECEPTION
        )
        return await self._reader.read(query)


__all__ = [
    "GetCurrentRecordValuesQuery",
    "GetCurrentRecordValuesUseCase",
]
