"""Applicationのchange_store_statusを定義する。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control.boundary_models import (
    Permission,
    ResolvedActorContext,
)
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.common.clock import BUSINESS_TIMEZONE, Clock
from app.application.common.exceptions import AuthorizationError
from app.application.common.organization_lock import OrganizationLock
from app.application.common.unit_of_work import UnitOfWork
from app.application.store.commands.dtos.get_store import StoreDto
from app.application.store.commands.services.support import load_store_or_raise
from app.application.store.interfaces.management import StoreWorkBoundary
from app.domain.corporate.identifiers import CorporateId
from app.domain.store.exceptions import StoreStateConflictError
from app.domain.store.identifiers import StoreId
from app.domain.store.primitives import (
    ManagerAssignmentStatus,
    StoreStatus,
    StoreStatusReason,
)
from app.domain.store.repositories import (
    StoreManagerAssignmentRepository,
    StoreRepository,
)


@dataclass(frozen=True, kw_only=True)
class ChangeStoreStatusCommand:
    """即時の店舗状態変更。記録者と記録時刻は入力として受けない。"""

    corporate_id: str
    store_id: str
    status: str
    reason: str


class ChangeStoreStatusUseCase:
    """残業務と任命の整理を同じUoWで状態変更へ反映する。"""

    def __init__(
        self,
        stores: StoreRepository,
        managers: StoreManagerAssignmentRepository,
        work: StoreWorkBoundary,
        access: CorporateAccessBoundary,
        clock: Clock,
        unit_of_work: UnitOfWork,
        lock: OrganizationLock,
    ) -> None:
        self._stores = stores
        self._managers = managers
        self._work = work
        self._access = access
        self._clock = clock
        self._unit_of_work = unit_of_work
        self._lock = lock

    async def execute(self, command: ChangeStoreStatusCommand) -> StoreDto:
        """操作者を付けて状態を変更する。"""
        self._unit_of_work.ensure_active()
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._lock.acquire("identity")
        await self._lock.acquire(f"corporate:{corporate_id.value}")
        await self._access.require_active(
            corporate_id=corporate_id, permission=Permission.MANAGE_STORE
        )
        store_id = StoreId.parse(command.store_id)
        store = await load_store_or_raise(
            self._stores, corporate_id=corporate_id, store_id=store_id
        )
        actor = self._access.actor
        if (
            not isinstance(actor, ResolvedActorContext)
            or actor.person_id is None
            or actor.account_id is None
        ):
            raise AuthorizationError(
                "店舗状態の変更には本人とアカウントの特定が必要です。"
            )
        if store.status == command.status:
            return StoreDto.from_entity(store)
        now = self._clock.now()
        updated = store.change_status(
            StoreStatus(command.status),
            reason=StoreStatusReason(command.reason),
            person_id=actor.person_id,
            account_id=actor.account_id,
            recorded_at=now,
        )
        if command.status == StoreStatus.CLOSED:
            if await self._work.has_unfinished(corporate_id, store_id):
                raise StoreStateConflictError(
                    "未完了の処方箋または調剤がある店舗は閉局できません。"
                )
            applied_on = now.astimezone(BUSINESS_TIMEZONE).date()
            for assignment in await self._managers.list_by_store(
                corporate_id, store_id
            ):
                if assignment.status != ManagerAssignmentStatus.CONFIRMED:
                    continue
                if assignment.period.starts_on > applied_on:
                    await self._managers.save(assignment.cancel(applied_on=applied_on))
                elif assignment.is_effective_on(applied_on):
                    await self._managers.save(assignment.end(ends_on=applied_on))
        await self._stores.save(updated)
        return StoreDto.from_entity(updated)
