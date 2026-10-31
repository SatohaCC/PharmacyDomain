"""Applicationのchange_membershipを定義する。"""

from __future__ import annotations

from dataclasses import replace

from app.application.access_control.boundary_models import (
    ActorRole,
    Permission,
    ResolvedActorContext,
)
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.access_control.policies import AuthorizationService
from app.application.common.clock import Clock, business_date
from app.application.common.exceptions import AuthorizationError, NotFoundError
from app.application.common.organization_lock import OrganizationLock
from app.application.common.unit_of_work import UnitOfWork
from app.application.identity.commands.dtos.identity_views import MembershipDto
from app.application.identity.commands.services.repositories import IdentityRepositories
from app.application.identity.commands.services.support import (
    ensure_administrator_preserved,
    validate_membership_target,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.identity.exceptions import IdentityConflictError
from app.domain.identity.identifiers import CorporateMembershipId
from app.domain.identity.primitives import AccountStatus, MembershipRole
from app.domain.staff.repositories import StaffRepository
from app.domain.store.identifiers import StoreId
from app.domain.store.repositories import (
    StoreManagerAssignmentRepository,
    StoreRepository,
)


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
        managers: StoreManagerAssignmentRepository,
        clock: Clock,
    ) -> None:
        self._repositories = repositories
        self._staff = staff
        self._stores = stores
        self._access = access
        self._unit_of_work = unit_of_work
        self._lock = lock
        self._managers = managers
        self._clock = clock

    async def execute(
        self,
        corporate_id: str,
        membership_id: str,
        *,
        status: str | None = None,
        role: str | None = None,
        store_ids: tuple[str, ...] | None = None,
        store_id: str | None = None,
        store_is_active: bool | None = None,
    ) -> MembershipDto:
        """指定した項目だけを変更し、管理者不在になる変更を拒否する。"""
        self._unit_of_work.ensure_active()
        corporate = CorporateId.parse(corporate_id)
        await self._lock.acquire("identity")
        await self._lock.acquire(f"corporate:{corporate.value}")
        actor = self._access.actor
        administrator = bool(
            actor.roles & {ActorRole.VENDOR_SYSTEM_ADMIN, ActorRole.CORPORATE_ADMIN}
        )
        permission = (
            Permission.MANAGE_STAFF if administrator else Permission.MANAGE_STORE_USERS
        )
        await self._access.require_active(corporate_id=corporate, permission=permission)
        target_store = StoreId.parse(store_id) if store_id is not None else None
        if not administrator:
            if target_store is None:
                raise AuthorizationError("店舗管理では対象店舗を指定してください。")
            AuthorizationService(actor).require_store(
                permission=Permission.MANAGE_STORE_USERS,
                target_corporate_id=corporate,
                target_store_id=target_store,
            )
        membership = await self._repositories.memberships.get(
            CorporateMembershipId.parse(membership_id)
        )
        if membership is None or membership.corporate_id != corporate:
            raise NotFoundError()
        if not administrator:
            assert isinstance(actor, ResolvedActorContext)
            appointment = (
                await self._managers.find_effective(
                    corporate, target_store, business_date(self._clock)
                )
                if target_store is not None
                else None
            )
            own_membership = (
                await self._repositories.memberships.get(actor.membership_id)
                if actor.membership_id is not None
                else None
            )
            own_account = (
                await self._repositories.accounts.get(actor.account_id)
                if actor.account_id is not None
                else None
            )
            if (
                appointment is None
                or appointment.staff_id != actor.staff_id
                or appointment.person_id != actor.person_id
                or own_membership is None
                or own_membership.account_id != actor.account_id
                or own_membership.status != AccountStatus.ACTIVE
                or target_store not in own_membership.active_store_ids
                or own_account is None
                or own_account.status != AccountStatus.ACTIVE
            ):
                raise AuthorizationError(
                    "現在有効な管理薬剤師の任命と利用権限が必要です。"
                )
            if target_store not in membership.store_ids:
                raise NotFoundError()
            if status is not None or role is not None:
                raise AuthorizationError(
                    "管理薬剤師は法人全体の状態・権限を変更できません。"
                )
            if store_ids is not None:
                requested = frozenset(StoreId.parse(item) for item in store_ids)
                if (requested ^ membership.store_ids) - {target_store}:
                    raise AuthorizationError("他店舗の権限を変更できません。")
            if membership.staff_id is not None:
                appointments = await self._managers.list_by_staff(
                    corporate, membership.staff_id
                )
                if any(
                    item.is_effective_on(business_date(self._clock))
                    for item in appointments
                ):
                    raise AuthorizationError(
                        "管理薬剤師の店舗権限は法人管理者が変更してください。"
                    )
        account = await self._repositories.accounts.get(membership.account_id)
        if account is None:
            raise NotFoundError()
        updated = replace(
            membership,
            status=AccountStatus(status) if status is not None else membership.status,
            role=MembershipRole(role) if role is not None else membership.role,
            store_ids=frozenset(StoreId.parse(item) for item in store_ids)
            if store_ids is not None
            else membership.store_ids,
            suspended_store_ids=membership.suspended_store_ids
            & (
                frozenset(StoreId.parse(item) for item in store_ids)
                if store_ids is not None
                else membership.store_ids
            ),
        )
        if target_store is None and store_is_active is not None:
            raise IdentityConflictError("店舗の利用状態には対象店舗が必要です。")
        if target_store is not None and store_is_active is not None:
            updated = updated.change_store_access(
                store_id=target_store, is_active=store_is_active
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
                store_ids=updated.store_ids
                if administrator
                else frozenset({target_store})
                if target_store is not None
                else frozenset(),
                staff_id=updated.staff_id,
                staff=self._staff,
                stores=self._stores,
                links=self._repositories.links,
            )
        if administrator:
            await ensure_administrator_preserved(
                corporate,
                memberships=self._repositories.memberships,
                accounts=self._repositories.accounts,
                updated_membership=updated,
            )
        await self._repositories.memberships.save(updated)
        return MembershipDto.from_entity(updated)
