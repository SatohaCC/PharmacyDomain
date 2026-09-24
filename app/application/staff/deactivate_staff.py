"""スタッフ無効化（退職等）ユースケース。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.application.access_control.boundary import CorporateAccessBoundary
from app.application.access_control.models import Permission
from app.application.staff.access_revocation import StaffAccessRevocationBoundary
from app.application.staff.support import load_staff_or_raise
from app.domain.corporate.primitives import CorporateId
from app.domain.staff.primitives import StaffId
from app.domain.staff.repository import StaffRepository


@dataclass(frozen=True, kw_only=True)
class DeactivateStaffCommand:
    """スタッフ無効化の入力データ（DTO）。"""

    corporate_id: str
    staff_id: str
    retired_on: date
    """退職日。継続中の店舗所属はこの日で終了する。

    既定値を置かない。``date.today()`` を暗黙に使うと、注入した ``Clock`` を
    迂回したうえで「いつ退職したか」が呼び出し時刻に化ける。退職日は
    所属履歴に残る業務事実なので、必ず呼び出し側が渡す。
    """


class DeactivateStaffUseCase:
    """スタッフ無効化（退職等）ユースケース。"""

    def __init__(
        self,
        repository: StaffRepository,
        corporate_access: CorporateAccessBoundary,
        access_revocation: StaffAccessRevocationBoundary,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access
        self._access_revocation = access_revocation

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

        updated_staff = staff.deactivate(command.retired_on)
        await self._repository.save(updated_staff)
        # 退職したのに法人アクセス権が残ると、退職者のアカウントで業務を続けられる。
        # 保存の境界へ隠さず、退職の手順として明示的に行う。
        await self._access_revocation.revoke_for(updated_staff)
