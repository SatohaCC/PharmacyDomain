"""Applicationのreactivate_accountを定義する。"""

from __future__ import annotations

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.access_control.policies import AuthorizationService
from app.application.common.exceptions import NotFoundError
from app.application.common.organization_lock import OrganizationLock
from app.application.common.unit_of_work import UnitOfWork
from app.application.identity.commands.dtos.identity_views import AccountDto
from app.application.identity.commands.services.repositories import IdentityRepositories
from app.domain.shared.actor import UserAccountId


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
