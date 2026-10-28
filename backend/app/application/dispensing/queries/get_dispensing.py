"""Applicationのget_dispensingを定義する。"""

from __future__ import annotations

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.dispensing.interfaces.get_dispensing_query_reader import (
    GetDispensingQueryReader,
)
from app.application.dispensing.queries.dtos.get_dispensing import DispensingProcessDto
from app.application.dispensing.queries.models import GetDispensingQuery
from app.domain.corporate.identifiers import CorporateId


class GetDispensingUseCase:
    def __init__(
        self,
        reader: GetDispensingQueryReader,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._reader = reader
        self._corporate_access = corporate_access

    async def execute(self, query: GetDispensingQuery) -> DispensingProcessDto:
        """指定法人の調剤セッションをDTOで返す。エンティティは返さない。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.VIEW_DISPENSING
        )
        return await self._reader.read(query)
