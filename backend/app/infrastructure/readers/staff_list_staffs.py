"""Repositoryから参照用DTOを投影するアダプタ。保存は行わない。"""

from __future__ import annotations

from app.application.staff.interfaces.list_staffs_query_reader import (
    ListStaffsQueryReader,
)
from app.application.staff.queries.dtos.list_staffs import StaffSummaryDto
from app.application.staff.queries.models import ListStaffsQuery
from app.domain.corporate.identifiers import CorporateId
from app.domain.staff.repositories import StaffCatalogRepository


class ListStaffsProjection(ListStaffsQueryReader):
    """認可済みの対象法人に所属するスタッフ一覧を取得するユースケース。"""

    def __init__(self, repository: StaffCatalogRepository) -> None:
        self._repository = repository

    async def read(self, query: ListStaffsQuery) -> list[StaffSummaryDto]:
        corporate_id = CorporateId.parse(query.corporate_id)
        staffs = await self._repository.list_by_corporate_id(corporate_id)
        return [StaffSummaryDto.from_entity(staff) for staff in staffs]
