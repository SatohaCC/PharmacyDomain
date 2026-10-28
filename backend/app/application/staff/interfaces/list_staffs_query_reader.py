"""Applicationのlist_staffs_query_readerを定義する。"""

from __future__ import annotations

from typing import Protocol

from app.application.staff.queries.dtos.list_staffs import StaffSummaryDto
from app.application.staff.queries.models import ListStaffsQuery


class ListStaffsQueryReader(Protocol):
    async def read(self, query: ListStaffsQuery) -> list[StaffSummaryDto]:
        """認可済みの検索条件から、不変な参照結果だけを返す。"""
        ...
