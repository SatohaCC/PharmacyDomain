"""Applicationのsuspend_accountを定義する。"""

from __future__ import annotations

from app.application.access_control.boundary_models import ActorRole, Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.common.exceptions import NotFoundError
from app.application.common.organization_lock import OrganizationLock
from app.application.common.unit_of_work import UnitOfWork
from app.application.identity.commands.dtos.identity_views import AccountDto
from app.application.identity.commands.services.repositories import IdentityRepositories
from app.application.identity.commands.services.support import (
    ensure_administrator_preserved,
)
from app.domain.shared.actor import UserAccountId


class SuspendAccountUseCase:
    """ベンダーまたは自法人の管理者が個人アカウントを停止する。

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
        actor = self._access.actor
        vendor = ActorRole.VENDOR_SYSTEM_ADMIN in actor.roles
        if not vendor:
            if actor.corporate_id is None:
                raise NotFoundError()
            await self._access.require_active(
                corporate_id=actor.corporate_id, permission=Permission.MANAGE_STAFF
            )
        await self._lock.acquire("identity")
        if not vendor:
            assert actor.corporate_id is not None
            await self._lock.acquire(f"corporate:{actor.corporate_id.value}")
            memberships = await self._repositories.memberships.list_by_corporate(
                actor.corporate_id
            )
            if not any(
                item.account_id == UserAccountId.parse(account_id)
                for item in memberships
            ):
                raise NotFoundError()
        account = await self._repositories.accounts.get(UserAccountId.parse(account_id))
        if account is None:
            raise NotFoundError()
        if not vendor and account.is_vendor_admin:
            raise NotFoundError()
        updated = account.suspend()
        membership = await self._repositories.memberships.find_active_for_account(
            account.id
        )
        if (
            not vendor
            and membership is not None
            and membership.corporate_id != actor.corporate_id
        ):
            raise NotFoundError()
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
