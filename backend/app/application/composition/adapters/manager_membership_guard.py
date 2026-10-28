"""管理薬剤師の任命期間中に、他店舗の利用権限を持たせない保存前境界。"""

from app.application.common.clock import Clock, business_date
from app.application.common.organization_lock import OrganizationLock
from app.domain.identity.entities import CorporateMembership
from app.domain.identity.repositories import CorporateMembershipRepository
from app.domain.store.entities import StoreManagerAssignment
from app.domain.store.exceptions import ManagerAssignmentConflictError
from app.domain.store.primitives import ManagerAssignmentStatus
from app.domain.store.repositories import StoreManagerAssignmentRepository


class ManagerMembershipWriteGuard:
    """任命と利用店舗の双方の保存経路で、一店舗への限定を確認する。"""

    def __init__(
        self,
        memberships: CorporateMembershipRepository,
        managers: StoreManagerAssignmentRepository,
        clock: Clock,
        lock: OrganizationLock,
    ) -> None:
        self._memberships = memberships
        self._managers = managers
        self._clock = clock
        self._lock = lock

    async def check(self, aggregate: object, is_new: bool) -> None:
        """任命と所属変更を同じ法人ロックで直列化する。"""
        if not isinstance(aggregate, (CorporateMembership, StoreManagerAssignment)):
            return
        await self._lock.acquire(f"corporate:{aggregate.corporate_id.value}")
        membership: CorporateMembership | None
        if isinstance(aggregate, CorporateMembership):
            if aggregate.staff_id is None:
                return
            membership = aggregate
            assignments = await self._managers.list_by_staff(
                aggregate.corporate_id, aggregate.staff_id
            )
        else:
            membership = await self._memberships.find_by_staff(aggregate.staff_id)
            assignments = [aggregate]
        if membership is None:
            return
        applied_on = business_date(self._clock)
        for assignment in assignments:
            if (
                assignment.status == ManagerAssignmentStatus.CONFIRMED
                and (
                    assignment.period.ends_on is None
                    or assignment.period.ends_on >= applied_on
                )
                and membership.store_ids != frozenset({assignment.store_id})
            ):
                raise ManagerAssignmentConflictError(
                    "管理薬剤師の利用店舗は任命された一店舗に限定してください。"
                )
