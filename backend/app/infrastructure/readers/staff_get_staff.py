"""Repositoryから参照用DTOを投影するアダプタ。保存は行わない。"""

from __future__ import annotations

from datetime import date

from app.application.staff.interfaces.get_staff_query_reader import GetStaffQueryReader
from app.application.staff.queries.dtos.get_staff import StaffDto
from app.application.staff.queries.dtos.list_staffs import StaffSummaryDto
from app.application.staff.queries.models import GetStaffQuery
from app.domain.corporate.identifiers import CorporateId
from app.domain.staff.identifiers import StaffId
from app.domain.staff.repositories import StaffRepository
from app.infrastructure.readers.helpers.staff_support import load_staff_or_raise


class GetStaffProjection(GetStaffQueryReader):
    """スタッフ詳細取得ユースケース。"""

    def __init__(self, repository: StaffRepository) -> None:
        self._repository = repository

    async def read(
        self, query: GetStaffQuery, *, include_private: bool, target_date: date | None
    ) -> StaffDto | StaffSummaryDto:
        corporate_id = CorporateId.parse(query.corporate_id)
        staff_id = StaffId.parse(query.staff_id)
        staff = await load_staff_or_raise(
            self._repository, corporate_id=corporate_id, staff_id=staff_id
        )
        if not include_private:
            return StaffSummaryDto.from_entity(staff)
        if target_date is None:
            raise ValueError("詳細表示には判定日が必要です。")
        return StaffDto.from_entity(staff, target_date=target_date)
