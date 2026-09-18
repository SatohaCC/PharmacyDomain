"""スタッフ更新と任命・法人アクセス権を一つの保存境界で調整する。"""

from zoneinfo import ZoneInfo

from app.application.common import UnitOfWork
from app.application.common.clock import Clock
from app.application.common.organization_lock import OrganizationLock
from app.domain.corporate.primitives import CorporateId
from app.domain.identity.administrator_service import LastAdministratorService
from app.domain.identity.repository import (
    CorporateMembershipRepository,
    UserAccountRepository,
)
from app.domain.staff.primitives import StaffCode, StaffId
from app.domain.staff.repository import StaffRepository
from app.domain.staff.staff import Staff
from app.domain.store.manager_assignment import ManagerAssignmentStatus
from app.domain.store.manager_repository import (
    ManagerAssignmentConflictError,
    StoreManagerAssignmentRepository,
)
from app.domain.store.manager_service import StoreManagerAssignmentService
from app.domain.store.repository import StoreRepository


class ManagedStaffRepository(StaffRepository):
    """読み込み前に競合を直列化し、退職時の権限停止を同じUoWへ含める。"""

    def __init__(
        self,
        staff: StaffRepository,
        stores: StoreRepository,
        managers: StoreManagerAssignmentRepository,
        memberships: CorporateMembershipRepository,
        accounts: UserAccountRepository,
        clock: Clock,
        work: UnitOfWork,
        lock: OrganizationLock,
    ) -> None:
        self._staff = staff
        self._stores = stores
        self._managers = managers
        self._memberships = memberships
        self._accounts = accounts
        self._clock = clock
        self._work = work
        self._lock = lock

    async def get(
        self, *, corporate_id: CorporateId, staff_id: StaffId
    ) -> Staff | None:
        """更新に使うスタッフは管理操作の共通ロック取得後に読む。"""
        self._work.ensure_active()
        await self._lock.acquire("identity")
        await self._lock.acquire(f"corporate:{corporate_id.value}")
        return await self._staff.get(corporate_id=corporate_id, staff_id=staff_id)

    async def exists_by_code(
        self,
        *,
        corporate_id: CorporateId,
        code: StaffCode,
        excluding_id: StaffId | None = None,
    ) -> bool:
        """コードの再利用を元Repositoryと同じ規則で調べる。"""
        return await self._staff.exists_by_code(
            corporate_id=corporate_id, code=code, excluding_id=excluding_id
        )

    async def save(self, staff: Staff) -> None:
        """任命整合性と最後の管理者を確認してスタッフと権限を保存する。"""
        self._work.ensure_active()
        await self._lock.acquire("identity")
        await self._lock.acquire(f"corporate:{staff.corporate_id.value}")
        today = self._clock.now().astimezone(ZoneInfo("Asia/Tokyo")).date()
        for assignment in await self._managers.list_by_staff(
            staff.corporate_id, staff.id
        ):
            if assignment.status != ManagerAssignmentStatus.CONFIRMED or (
                assignment.period.ends_on is not None
                and assignment.period.ends_on < today
            ):
                continue
            store = await self._stores.get(assignment.store_id)
            if store is None:
                raise ManagerAssignmentConflictError("任命された店舗が見つかりません。")
            StoreManagerAssignmentService().ensure_assignable(
                assignment, store=store, staff=staff
            )
        membership = await self._memberships.find_by_staff(staff.id)
        suspended = None
        if not staff.is_active and membership is not None:
            suspended = membership.suspend()
            memberships = await self._memberships.list_by_corporate(staff.corporate_id)
            accounts = []
            for item in memberships:
                account = await self._accounts.get(item.account_id)
                if account is not None:
                    accounts.append(account)
            LastAdministratorService().ensure_preserved(
                corporate_id=staff.corporate_id,
                previous_memberships=memberships,
                previous_accounts=accounts,
                updated_memberships=[
                    suspended if item.id == suspended.id else item
                    for item in memberships
                ],
                updated_accounts=accounts,
            )
        await self._staff.save(staff)
        if suspended is not None:
            await self._memberships.save(suspended)
