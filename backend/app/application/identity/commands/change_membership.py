"""Applicationのchange_membershipを定義する。"""

from __future__ import annotations

from dataclasses import replace

from app.application.access_control.boundary_models import (
    ActorRole,
    Permission,
    ResolvedActorContext,
    StoreRoleInput,
)
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.access_control.policies import AuthorizationService
from app.application.common.clock import Clock, business_date
from app.application.common.exceptions import AuthorizationError, NotFoundError
from app.application.common.organization_lock import OrganizationLock
from app.application.common.unit_of_work import UnitOfWork
from app.application.identity.boundary_models import StoreWorkConditionChange
from app.application.identity.commands.dtos.identity_views import MembershipDto
from app.application.identity.commands.services.repositories import IdentityRepositories
from app.application.identity.commands.services.support import (
    ensure_administrator_preserved,
    validate_membership_target,
)
from app.application.identity.interfaces.staff_store_settings import (
    StaffStoreSettingsBoundary,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.identity.exceptions import IdentityConflictError
from app.domain.identity.identifiers import CorporateMembershipId
from app.domain.identity.primitives import AccountStatus, MembershipRole, StoreRole
from app.domain.identity.value_objects import StoreRoleAssignment
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
        staff_store_settings: StaffStoreSettingsBoundary,
    ) -> None:
        self._repositories = repositories
        self._staff = staff
        self._stores = stores
        self._access = access
        self._unit_of_work = unit_of_work
        self._lock = lock
        self._managers = managers
        self._clock = clock
        self._staff_store_settings = staff_store_settings

    async def execute(
        self,
        corporate_id: str,
        membership_id: str,
        *,
        status: str | None = None,
        role: str | None = None,
        store_roles: tuple[StoreRoleInput, ...] | None = None,
        store_id: str | None = None,
        store_is_active: bool | None = None,
        store_work_conditions: tuple[StoreWorkConditionChange, ...] = (),
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
            if store_roles is not None:
                before = {
                    item.store_id: item.role
                    for item in membership.store_roles
                    if item.store_id != target_store
                }
                requested = {
                    StoreId.parse(item.store_id): StoreRole(item.role)
                    for item in store_roles
                    if StoreId.parse(item.store_id) != target_store
                }
                if requested != before:
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
            store_roles=tuple(
                StoreRoleAssignment(
                    store_id=StoreId.parse(item.store_id), role=StoreRole(item.role)
                )
                for item in store_roles
            )
            if store_roles is not None
            else membership.store_roles,
            suspended_store_ids=membership.suspended_store_ids
            & (
                frozenset(StoreId.parse(item.store_id) for item in store_roles)
                if store_roles is not None
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
        if store_work_conditions:
            ids = [StoreId.parse(item.store_id) for item in store_work_conditions]
            if len(ids) != len(set(ids)) or not set(ids) <= updated.store_ids:
                raise DomainValidationError(
                    "勤務条件は選択した店舗ごとに一件ずつ指定してください。"
                )
            if not administrator and any(item != target_store for item in ids):
                raise AuthorizationError("他店舗の勤務条件を変更できません。")
            if updated.staff_id is None:
                raise DomainValidationError("勤務条件にはスタッフの紐付けが必要です。")
            await self._staff_store_settings.apply(
                corporate, updated.staff_id, store_work_conditions
            )
        await self._repositories.memberships.save(updated)
        return MembershipDto.from_entity(updated)
