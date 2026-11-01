"""Applicationのupdate_staff_employmentを定義する。"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.staff.commands.services.support import load_staff_or_raise
from app.domain.corporate.identifiers import CorporateId
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.staff.identifiers import StaffId
from app.domain.staff.primitives import EmploymentType, WeeklyContractHours
from app.domain.staff.repositories import StaffRepository


@dataclass(frozen=True, kw_only=True)
class UpdateStaffEmploymentCommand:
    """スタッフ労働契約変更コマンド。"""

    corporate_id: str
    staff_id: str
    employment_type: str
    weekly_contract_hours: float | None = None


class UpdateStaffEmploymentUseCase:
    """スタッフ労働契約変更ユースケース。"""

    def __init__(
        self, repository: StaffRepository, corporate_access: CorporateAccessBoundary
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access

    async def execute(self, command: UpdateStaffEmploymentCommand) -> None:
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.MANAGE_STAFF
        )
        staff_id = StaffId.parse(command.staff_id)
        staff = await load_staff_or_raise(
            self._repository, corporate_id=corporate_id, staff_id=staff_id
        )

        try:
            emp_type = EmploymentType(command.employment_type)
        except ValueError as err:
            raise DomainValidationError(
                f"不正な雇用形態です: '{command.employment_type}'"
            ) from err

        weekly_hours = (
            WeeklyContractHours(Decimal(str(command.weekly_contract_hours)))
            if command.weekly_contract_hours is not None
            else None
        )

        updated = staff.change_employment_type(emp_type).change_weekly_contract_hours(
            weekly_hours
        )
        await self._repository.save(updated)
