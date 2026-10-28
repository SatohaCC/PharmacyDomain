"""Applicationのchange_staff_job_titleを定義する。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.common.input_normalization import to_optional_text
from app.application.staff.commands.services.support import load_staff_or_raise
from app.domain.corporate.identifiers import CorporateId
from app.domain.staff.identifiers import StaffId
from app.domain.staff.primitives import JobTitle
from app.domain.staff.repositories import StaffRepository


@dataclass(frozen=True, kw_only=True)
class ChangeStaffJobTitleCommand:
    """役職・肩書変更の入力データ（DTO）。"""

    corporate_id: str
    staff_id: str
    job_title: str | None = None


class ChangeStaffJobTitleUseCase:
    """スタッフ役職・肩書変更ユースケース。"""

    def __init__(
        self, repository: StaffRepository, corporate_access: CorporateAccessBoundary
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access

    async def execute(self, command: ChangeStaffJobTitleCommand) -> None:
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.MANAGE_STAFF
        )
        staff_id = StaffId.parse(command.staff_id)
        staff = await load_staff_or_raise(
            self._repository, corporate_id=corporate_id, staff_id=staff_id
        )
        raw_job_title = to_optional_text(command.job_title)
        job_title = JobTitle(raw_job_title) if raw_job_title else None
        updated_staff = staff.change_job_title(job_title)
        await self._repository.save(updated_staff)
