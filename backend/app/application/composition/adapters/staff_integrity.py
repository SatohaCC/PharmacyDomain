"""Applicationのstaff_integrityを定義する。"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date

from app.application.common.clock import Clock, business_date
from app.application.common.organization_lock import OrganizationLock
from app.application.composition.adapters.organization_snapshot_mapping import (
    manager_staff_source,
)
from app.application.staff.interfaces.access_revocation import (
    StaffAccessRevocationBoundary,
)
from app.domain.identity.entities import CorporateMembership
from app.domain.identity.repositories import (
    CorporateMembershipRepository,
    UserAccountRepository,
)
from app.domain.identity.services import LastAdministratorService
from app.domain.staff.entities import Staff
from app.domain.store.entities import StoreManagerAssignment
from app.domain.store.exceptions import ManagerAssignmentConflictError
from app.domain.store.primitives import ManagerAssignmentStatus
from app.domain.store.repositories import (
    StoreManagerAssignmentRepository,
    StoreRepository,
)
from app.domain.store.services import StoreManagerAssignmentService


def _is_in_force(assignment: StoreManagerAssignment, applied_on: date) -> bool:
    """適用日より後にも及ぶ確定任命か。

    終了日が適用日**以前**の任命は決着した履歴である。終了日当日を対象に残すと、
    任命を今日付で終了したその日に退職できない（在任中の任命として検証され、
    無効化済みのスタッフが要件を満たさないと判定される）。任命期間は終了日を
    含む閉区間なので、最終日まで務めた任命と、その日の退職は両立する。
    """
    if assignment.status != ManagerAssignmentStatus.CONFIRMED:
        return False
    ends_on = assignment.period.ends_on
    return ends_on is None or ends_on > applied_on


class StaffAssignmentWriteGuard:
    """保存されるスタッフが、在任中の任命を成立させ続けることを確かめる。

    資格の削除・所属の変更・退職は、どれも管理薬剤師の要件を壊しうる。検証を
    個々のユースケースへ書き写すと、次に増えたユースケースだけが素通りする。
    保存の手前に置けば、スタッフを書く経路すべてに自動で掛かる。
    """

    def __init__(
        self,
        stores: StoreRepository,
        managers: StoreManagerAssignmentRepository,
        clock: Clock,
        lock: OrganizationLock,
    ) -> None:
        self._stores = stores
        self._managers = managers
        self._clock = clock
        self._lock = lock

    async def check(self, aggregate: object, is_new: bool) -> None:
        """スタッフの保存だけを対象に、在任中の任命を検証する。

        読み出しの前に法人の管理ロックを取る。任命を書く側（``ManageStoreManager``）
        は同じキーを実行の冒頭で取るので、これが無いと両者が相手の確定前の状態を
        読んで**どちらも成功する**。資格を失ったスタッフが管理薬剤師のまま残り、
        例外は出ない。ロックはスタッフを書く経路だけで取り、参照では取らない。
        """
        if not isinstance(aggregate, Staff):
            return
        await self._lock.acquire(f"corporate:{aggregate.corporate_id.value}")
        applied_on = business_date(self._clock)
        service = StoreManagerAssignmentService()
        for assignment in await self._managers.list_by_staff(
            aggregate.corporate_id, aggregate.id
        ):
            if not _is_in_force(assignment, applied_on):
                continue
            store = await self._stores.get(assignment.store_id)
            if store is None:
                raise ManagerAssignmentConflictError("任命された店舗が見つかりません。")
            service.ensure_assignable(
                assignment, store=store, staff=manager_staff_source(aggregate)
            )


def _replaced(
    memberships: Iterable[CorporateMembership], updated: CorporateMembership
) -> list[CorporateMembership]:
    """一覧のうち、同じIDの要素だけを差し替える。"""
    return [updated if item.id == updated.id else item for item in memberships]


class StaffAccessRevocationService(StaffAccessRevocationBoundary):
    """退職したスタッフの法人アクセス権を、同じトランザクションで停止する。"""

    def __init__(
        self,
        memberships: CorporateMembershipRepository,
        accounts: UserAccountRepository,
        lock: OrganizationLock,
    ) -> None:
        self._memberships = memberships
        self._accounts = accounts
        self._lock = lock

    async def revoke_for(self, staff: Staff) -> None:
        """退職済みのスタッフに対応する法人アクセス権を停止する。

        最後の有効な法人管理者を失う退職は拒否する。判定と停止を同じロックの
        内側で行わないと、2人の管理者が同時に退職して両方とも成立する。
        有効なスタッフに対しては何もしない（再雇用で権限は復活させない）。
        """
        if staff.is_active:
            return
        await self._lock.acquire(f"corporate:{staff.corporate_id.value}")
        membership = await self._memberships.find_by_staff(staff.id)
        if membership is None:
            return
        suspended = membership.suspend()
        memberships = await self._memberships.list_by_corporate(staff.corporate_id)
        accounts = await self._accounts.list_by_ids(
            {item.account_id for item in memberships}
        )
        LastAdministratorService().ensure_preserved(
            corporate_id=staff.corporate_id,
            previous_memberships=memberships,
            previous_accounts=accounts,
            updated_memberships=_replaced(memberships, suspended),
            updated_accounts=accounts,
        )
        await self._memberships.save(suspended)
