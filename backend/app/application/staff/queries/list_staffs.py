"""Applicationのlist_staffsを定義する。"""

from __future__ import annotations

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.staff.interfaces.list_staffs_query_reader import (
    ListStaffsQueryReader,
)
from app.application.staff.queries.dtos.list_staffs import StaffSummaryDto
from app.application.staff.queries.models import ListStaffsQuery
from app.domain.corporate.identifiers import CorporateId


class ListStaffsUseCase:
    def __init__(
        self, reader: ListStaffsQueryReader, corporate_access: CorporateAccessBoundary
    ) -> None:
        self._reader = reader
        self._corporate_access = corporate_access

    async def execute(self, query: ListStaffsQuery) -> list[StaffSummaryDto]:
        corporate_id = CorporateId.parse(query.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.VIEW_STAFF
        )
        return await self._reader.read(query)
