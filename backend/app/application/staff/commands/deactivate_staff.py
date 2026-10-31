"""Applicationのdeactivate_staffを定義する。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.common.clock import Clock, business_date
from app.application.staff.commands.services.support import load_staff_or_raise
from app.application.staff.interfaces.access_revocation import (
    StaffAccessRevocationBoundary,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.staff.identifiers import StaffId
from app.domain.staff.repositories import StaffRepository


@dataclass(frozen=True, kw_only=True)
class DeactivateStaffCommand:
    """スタッフ無効化の入力データ（DTO）。"""

    corporate_id: str
    staff_id: str
    retired_on: date
    "退職日。継続中の店舗所属はこの日で終了する。\n\n    既定値を置かない。``date.today()`` を暗黙に使うと、注入した ``Clock`` を\n    迂回したうえで「いつ退職したか」が呼び出し時刻に化ける。退職日は\n    所属履歴に残る業務事実なので、必ず呼び出し側が渡す。\n    "


class DeactivateStaffUseCase:
    """スタッフ無効化（退職等）ユースケース。"""

    def __init__(
        self,
        repository: StaffRepository,
        corporate_access: CorporateAccessBoundary,
        access_revocation: StaffAccessRevocationBoundary,
        clock: Clock,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access
        self._access_revocation = access_revocation
        self._clock = clock

    async def execute(self, command: DeactivateStaffCommand) -> None:
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.MANAGE_STAFF
        )
        if command.retired_on > business_date(self._clock):
            raise DomainValidationError("退職日に未来日は指定できません。")
        staff_id = StaffId.parse(command.staff_id)
        staff = await load_staff_or_raise(
            self._repository, corporate_id=corporate_id, staff_id=staff_id
        )
        updated_staff = staff.deactivate(command.retired_on)
        await self._repository.save(updated_staff)
        await self._access_revocation.revoke_for(updated_staff)
