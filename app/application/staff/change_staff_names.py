"""スタッフ氏名変更ユースケース。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control import (
    CorporateAccessBoundary,
    Permission,
)
from app.application.staff.support import load_staff_or_raise
from app.base.domain.value_object import PersonNames
from app.domain.corporate.primitives import CorporateId
from app.domain.staff.primitives import StaffId
from app.domain.staff.repository import StaffRepository


@dataclass(frozen=True, kw_only=True)
class ChangeStaffNamesCommand:
    """氏名変更の入力データ（DTO）。"""

    corporate_id: str
    staff_id: str
    last_name: str
    first_name: str
    last_name_kana: str
    first_name_kana: str


class ChangeStaffNamesUseCase:
    """スタッフ氏名変更ユースケース。"""

    def __init__(
        self,
        repository: StaffRepository,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access

    async def execute(self, command: ChangeStaffNamesCommand) -> None:
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

        names = PersonNames.create(
            last_name=command.last_name,
            first_name=command.first_name,
            last_name_kana=command.last_name_kana,
            first_name_kana=command.first_name_kana,
        )

        updated_staff = staff.change_names(names)
        await self._repository.save(updated_staff)
