"""スタッフ無効化（退職等）ユースケース。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control import (
    CorporateAccessBoundary,
    Permission,
)
from app.application.staff.support import load_staff_or_raise
from app.domain.corporate.primitives import CorporateId
from app.domain.staff import StaffId, StaffRepository


@dataclass(frozen=True, kw_only=True)
class DeactivateStaffCommand:
    """スタッフ無効化の入力データ（DTO）。"""

    corporate_id: str
    staff_id: str


class DeactivateStaffUseCase:
    """スタッフ無効化（退職等）ユースケース。"""

    def __init__(
        self,
        repository: StaffRepository,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access

    async def execute(self, command: DeactivateStaffCommand) -> None:
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

        updated_staff = staff.deactivate()
        await self._repository.save(updated_staff)
