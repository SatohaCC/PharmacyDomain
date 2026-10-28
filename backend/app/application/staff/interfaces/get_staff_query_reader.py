"""Applicationのget_staff_query_readerを定義する。"""

from __future__ import annotations

from datetime import date
from typing import Protocol

from app.application.staff.queries.dtos.get_staff import StaffDto
from app.application.staff.queries.dtos.list_staffs import StaffSummaryDto
from app.application.staff.queries.models import GetStaffQuery


class GetStaffQueryReader(Protocol):
    async def read(
        self, query: GetStaffQuery, *, include_private: bool, target_date: date | None
    ) -> StaffDto | StaffSummaryDto:
        """認可済みの検索条件から、不変な参照結果だけを返す。"""
        ...
