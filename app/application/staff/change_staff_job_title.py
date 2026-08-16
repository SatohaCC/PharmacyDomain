"""スタッフ役職・肩書変更ユースケース。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control import (
    CorporateAccessBoundary,
    Permission,
)
from app.application.staff.support import load_staff_or_raise, to_optional_text
from app.domain.corporate.primitives import CorporateId
from app.domain.staff import JobTitle, StaffId, StaffRepository


@dataclass(frozen=True, kw_only=True)
class ChangeStaffJobTitleCommand:
    """役職・肩書変更の入力データ（DTO）。"""

    corporate_id: str
    staff_id: str
    job_title: str | None = None


class ChangeStaffJobTitleUseCase:
    """スタッフ役職・肩書変更ユースケース。"""

    def __init__(
        self,
        repository: StaffRepository,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access

    async def execute(self, command: ChangeStaffJobTitleCommand) -> None:
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.MANAGE_STAFF,
        )
        staff_id = StaffId.parse(command.staff_id)

        staff = await load_staff_or_raise(
            self._repository,
            corporate_id=corporate_id,
            staff_id=staff_id,
        )

        raw_job_title = to_optional_text(command.job_title)
        job_title = JobTitle(raw_job_title) if raw_job_title else None

        updated_staff = staff.change_job_title(job_title)
        await self._repository.save(updated_staff)
