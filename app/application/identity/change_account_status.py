"""個人アカウント全体の停止・再開ユースケース。"""

from app.application.access_control.boundary import CorporateAccessBoundary
from app.application.access_control.models import Permission
from app.application.access_control.policy import AuthorizationService
from app.application.common.exceptions import NotFoundError
from app.application.common.organization_lock import OrganizationLock
from app.application.common.unit_of_work import UnitOfWork
from app.application.identity.dto import AccountDto
from app.application.identity.support import (
    IdentityRepositories,
    ensure_administrator_preserved,
)
from app.domain.identity.primitives import UserAccountId


class SuspendAccountUseCase:
    """個人アカウントそのものを停止する。ベンダー専用。

    法人アクセス権の停止と違い、こちらは本人が持つ全ての法人での利用を止める。
    最後の有効な法人管理者を失う停止は拒否する。
    """

    def __init__(
        self,
        repositories: IdentityRepositories,
        access: CorporateAccessBoundary,
        unit_of_work: UnitOfWork,
        lock: OrganizationLock,
    ) -> None:
        self._repositories = repositories
        self._access = access
        self._unit_of_work = unit_of_work
        self._lock = lock

    async def execute(self, account_id: str) -> AccountDto:
        """停止後も本人との対応は残す（監査の追跡を切らない）。"""
        self._unit_of_work.ensure_active()
        AuthorizationService(self._access.actor).require_vendor_system_admin(
            permission=Permission.REGISTER_CORPORATE
        )
        await self._lock.acquire("identity")
        account = await self._repositories.accounts.get(UserAccountId.parse(account_id))
        if account is None:
            raise NotFoundError()
        updated = account.suspend()
        membership = await self._repositories.memberships.find_active_for_account(
            account.id
        )
        if membership is not None:
            await self._lock.acquire(f"corporate:{membership.corporate_id.value}")
            await ensure_administrator_preserved(
                membership.corporate_id,
                memberships=self._repositories.memberships,
                accounts=self._repositories.accounts,
                updated_account=updated,
            )
        await self._repositories.accounts.save(updated)
        return AccountDto.from_entity(updated)


class ReactivateAccountUseCase:
    """停止した個人アカウントを再開する。ベンダー専用。

    アカウントの再開は法人アクセス権を復活させない。停止されていた権限を戻すかは
    その法人の判断なので、``ChangeMembershipUseCase`` で別に行う。
    """

    def __init__(
        self,
        repositories: IdentityRepositories,
        access: CorporateAccessBoundary,
        unit_of_work: UnitOfWork,
        lock: OrganizationLock,
    ) -> None:
        self._repositories = repositories
        self._access = access
        self._unit_of_work = unit_of_work
        self._lock = lock

    async def execute(self, account_id: str) -> AccountDto:
        """本人への参照を維持したまま利用を再開する。"""
        self._unit_of_work.ensure_active()
        AuthorizationService(self._access.actor).require_vendor_system_admin(
            permission=Permission.REGISTER_CORPORATE
        )
        await self._lock.acquire("identity")
        account = await self._repositories.accounts.get(UserAccountId.parse(account_id))
        if account is None:
            raise NotFoundError()
        updated = account.reactivate()
        await self._repositories.accounts.save(updated)
        return AccountDto.from_entity(updated)


__all__ = ["ReactivateAccountUseCase", "SuspendAccountUseCase"]
