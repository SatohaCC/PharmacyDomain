"""法人アクセス権の状態・ロール・店舗範囲を変更するユースケース。"""

from dataclasses import replace

from app.application.access_control.boundary import CorporateAccessBoundary
from app.application.access_control.models import Permission
from app.application.common.exceptions import NotFoundError
from app.application.common.organization_lock import OrganizationLock
from app.application.common.unit_of_work import UnitOfWork
from app.application.identity.dto import MembershipDto
from app.application.identity.support import (
    IdentityRepositories,
    ensure_administrator_preserved,
    validate_membership_target,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.identity.exceptions import IdentityConflictError
from app.domain.identity.primitives import (
    AccountStatus,
    CorporateMembershipId,
    MembershipRole,
)
from app.domain.staff.repository import StaffRepository
from app.domain.store.primitives import StoreId
from app.domain.store.repository import StoreRepository


class ChangeMembershipUseCase:
    """最後の管理者と本人対応を守って法人アクセス権を変更する。

    停止済みの個人アカウントに対して法人アクセス権だけを有効化できると、
    アカウント停止が実質的に無効になる。有効化のときだけ土台の状態も確かめる。
    """

    def __init__(
        self,
        repositories: IdentityRepositories,
        staff: StaffRepository,
        stores: StoreRepository,
        access: CorporateAccessBoundary,
        unit_of_work: UnitOfWork,
        lock: OrganizationLock,
    ) -> None:
        self._repositories = repositories
        self._staff = staff
        self._stores = stores
        self._access = access
        self._unit_of_work = unit_of_work
        self._lock = lock

    async def execute(
        self,
        corporate_id: str,
        membership_id: str,
        *,
        status: AccountStatus | None = None,
        role: MembershipRole | None = None,
        store_ids: tuple[str, ...] | None = None,
    ) -> MembershipDto:
        """指定した項目だけを変更し、管理者不在になる変更を拒否する。"""
        self._unit_of_work.ensure_active()
        corporate = CorporateId.parse(corporate_id)
        await self._lock.acquire("identity")
        await self._lock.acquire(f"corporate:{corporate.value}")
        await self._access.require_active(
            corporate_id=corporate, permission=Permission.MANAGE_STAFF
        )
        membership = await self._repositories.memberships.get(
            CorporateMembershipId.parse(membership_id)
        )
        if membership is None or membership.corporate_id != corporate:
            raise NotFoundError()
        account = await self._repositories.accounts.get(membership.account_id)
        if account is None:
            raise NotFoundError()
        updated = replace(
            membership,
            status=status if status is not None else membership.status,
            role=role if role is not None else membership.role,
            store_ids=frozenset(StoreId.parse(item) for item in store_ids)
            if store_ids is not None
            else membership.store_ids,
        )
        if updated.status == AccountStatus.ACTIVE:
            if account.status != AccountStatus.ACTIVE:
                raise IdentityConflictError(
                    "停止中のアカウントへアクセス権を有効化できません。"
                )
            await validate_membership_target(
                person_id=account.person_id,
                corporate_id=corporate,
                role=updated.role,
                store_ids=updated.store_ids,
                staff_id=updated.staff_id,
                staff=self._staff,
                stores=self._stores,
                links=self._repositories.links,
            )
        await ensure_administrator_preserved(
            corporate,
            memberships=self._repositories.memberships,
            accounts=self._repositories.accounts,
            updated_membership=updated,
        )
        await self._repositories.memberships.save(updated)
        return MembershipDto.from_entity(updated)


__all__ = ["ChangeMembershipUseCase"]
