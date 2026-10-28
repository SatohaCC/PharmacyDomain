"""Applicationのget_staffを定義する。"""

from __future__ import annotations

from app.application.access_control.boundary_models import ActorRole, Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.common.clock import Clock, business_date
from app.application.staff.interfaces.get_staff_query_reader import GetStaffQueryReader
from app.application.staff.queries.dtos.get_staff import StaffDto
from app.application.staff.queries.dtos.list_staffs import StaffSummaryDto
from app.application.staff.queries.models import GetStaffQuery
from app.domain.corporate.identifiers import CorporateId
from app.domain.staff.identifiers import StaffId


class GetStaffUseCase:
    def __init__(
        self,
        reader: GetStaffQueryReader,
        corporate_access: CorporateAccessBoundary,
        clock: Clock,
    ) -> None:
        self._reader = reader
        self._corporate_access = corporate_access
        self._clock = clock

    async def execute(self, query: GetStaffQuery) -> StaffDto | StaffSummaryDto:
        corporate_id = CorporateId.parse(query.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.VIEW_STAFF
        )
        StaffId.parse(query.staff_id)
        include_private = bool(
            self._corporate_access.actor.roles
            & {ActorRole.VENDOR_SYSTEM_ADMIN, ActorRole.CORPORATE_ADMIN}
        )
        target_date = (
            query.target_date or business_date(self._clock) if include_private else None
        )
        return await self._reader.read(
            query, include_private=include_private, target_date=target_date
        )
