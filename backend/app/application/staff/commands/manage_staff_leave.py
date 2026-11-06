"""Applicationのmanage_staff_leaveを定義する。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.staff.commands.services.support import load_staff_or_raise
from app.domain.corporate.identifiers import CorporateId
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.staff.identifiers import StaffId
from app.domain.staff.primitives import LeaveReason
from app.domain.staff.repositories import StaffRepository


@dataclass(frozen=True, kw_only=True)
class StartStaffLeaveCommand:
    """スタッフ休職開始コマンド。"""

    corporate_id: str
    staff_id: str
    leave_reason: str
    left_on: date


@dataclass(frozen=True, kw_only=True)
class ReturnStaffFromLeaveCommand:
    """スタッフ復職コマンド。"""

    corporate_id: str
    staff_id: str


class StartStaffLeaveUseCase:
    """スタッフ休職開始ユースケース。"""

    def __init__(
        self, repository: StaffRepository, corporate_access: CorporateAccessBoundary
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access

    async def execute(self, command: StartStaffLeaveCommand) -> None:
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.MANAGE_STAFF
        )
        staff_id = StaffId.parse(command.staff_id)
        staff = await load_staff_or_raise(
            self._repository, corporate_id=corporate_id, staff_id=staff_id
        )

        try:
            reason = LeaveReason(command.leave_reason)
        except ValueError as err:
            raise DomainValidationError(
                f"不正な休職理由です: '{command.leave_reason}'"
            ) from err

        updated = staff.start_leave(reason=reason, left_on=command.left_on)
        await self._repository.save(updated)


class ReturnStaffFromLeaveUseCase:
    """スタッフ復職ユースケース。"""

    def __init__(
        self, repository: StaffRepository, corporate_access: CorporateAccessBoundary
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access

    async def execute(self, command: ReturnStaffFromLeaveCommand) -> None:
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.MANAGE_STAFF
        )
        staff_id = StaffId.parse(command.staff_id)
        staff = await load_staff_or_raise(
            self._repository, corporate_id=corporate_id, staff_id=staff_id
        )

        updated = staff.return_from_leave()
        await self._repository.save(updated)
