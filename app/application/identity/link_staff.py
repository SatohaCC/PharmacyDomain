"""スタッフと本人の対応を固定するユースケース。"""

from app.application.access_control import CorporateAccessBoundary, Permission
from app.application.common import UnitOfWork
from app.application.common.exceptions import NotFoundError
from app.application.common.organization_lock import OrganizationLock
from app.application.identity.dto import StaffPersonDto
from app.domain.corporate.primitives import CorporateId
from app.domain.identity.exceptions import IdentityConflictError
from app.domain.identity.primitives import AccountPersonId
from app.domain.identity.repository import (
    AccountPersonRepository,
    StaffPersonLinkRepository,
)
from app.domain.identity.staff_person_link import StaffPersonLink
from app.domain.staff.primitives import StaffId
from app.domain.staff.repository import StaffRepository


class LinkStaffPersonUseCase:
    """管理者が明示した本人とStaffの対応を、変更不可として記録する。

    同じ対応を二重に登録しても成功として扱う（同じ結果になる操作を失敗に
    させない）。別人への付け替えだけを拒否する。
    """

    def __init__(
        self,
        people: AccountPersonRepository,
        links: StaffPersonLinkRepository,
        staff: StaffRepository,
        access: CorporateAccessBoundary,
        unit_of_work: UnitOfWork,
        lock: OrganizationLock,
    ) -> None:
        self._people = people
        self._links = links
        self._staff = staff
        self._access = access
        self._unit_of_work = unit_of_work
        self._lock = lock

    async def execute(
        self, corporate_id: str, person_id: str, staff_id: str
    ) -> StaffPersonDto:
        """既存の本人とStaffを対応させ、別人への付け替えを拒否する。"""
        self._unit_of_work.ensure_active()
        corporate = CorporateId.parse(corporate_id)
        await self._lock.acquire("identity")
        await self._lock.acquire(f"corporate:{corporate.value}")
        await self._access.require_active(
            corporate_id=corporate, permission=Permission.MANAGE_STAFF
        )
        person = await self._people.get(AccountPersonId.parse(person_id))
        staff = await self._staff.get(
            corporate_id=corporate, staff_id=StaffId.parse(staff_id)
        )
        if person is None or staff is None or staff.corporate_id != corporate:
            raise NotFoundError()
        existing = await self._links.get(staff.id)
        if existing is not None:
            if existing.person_id != person.id or existing.corporate_id != corporate:
                raise IdentityConflictError(
                    "スタッフを別の本人へ付け替えることはできません。"
                )
            return StaffPersonDto.from_entity(existing)
        link = StaffPersonLink(id=staff.id, corporate_id=corporate, person_id=person.id)
        await self._links.save(link)
        return StaffPersonDto.from_entity(link)


__all__ = ["LinkStaffPersonUseCase"]
