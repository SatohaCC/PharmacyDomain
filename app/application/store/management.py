"""店舗の状態と期間付き管理薬剤師の管理入力。"""

from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum
from typing import Protocol
from zoneinfo import ZoneInfo

from app.application.access_control import CorporateAccessBoundary, Permission
from app.application.access_control.models import ResolvedActorContext
from app.application.common import UnitOfWork
from app.application.common.clock import Clock
from app.application.common.exceptions import AuthorizationError, NotFoundError
from app.application.common.organization_lock import OrganizationLock
from app.application.store.get_store import StoreDto
from app.application.store.support import load_store_or_raise
from app.domain.corporate.primitives import CorporateId
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.staff.primitives import StaffId
from app.domain.staff.repository import StaffRepository
from app.domain.store.lifecycle import StoreStatus, StoreStatusReason
from app.domain.store.manager_assignment import (
    ManagerAssignmentPeriod,
    ManagerAssignmentStatus,
    StoreManagerAssignment,
    StoreManagerAssignmentId,
)
from app.domain.store.manager_repository import (
    ManagerAssignmentConflictError,
    StoreManagerAssignmentRepository,
)
from app.domain.store.manager_service import StoreManagerAssignmentService
from app.domain.store.primitives import StoreId
from app.domain.store.repository import StoreRepository


class StoreWorkBoundary(Protocol):
    """店舗に残っている未完了の処方箋・調剤を照会する。"""

    async def has_unfinished(
        self, corporate_id: CorporateId, store_id: StoreId
    ) -> bool:
        """対象法人・店舗の未完了業務が一件でもあれば真を返す。"""
        ...


@dataclass(frozen=True, kw_only=True)
class ChangeStoreStatusCommand:
    """即時の店舗状態変更。記録者と記録時刻は入力として受けない。"""

    corporate_id: str
    store_id: str
    status: StoreStatus
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
        if not isinstance(actor, ResolvedActorContext):
            raise AuthorizationError(
                "店舗状態の変更には本人とアカウントの特定が必要です。"
            )
        if store.status == command.status:
            return StoreDto.from_entity(store)
        now = self._clock.now()
        updated = store.change_status(
            command.status,
            reason=StoreStatusReason(command.reason),
            person_id=actor.person_id,
            account_id=actor.account_id,
            recorded_at=now,
        )
        if command.status == StoreStatus.CLOSED:
            if await self._work.has_unfinished(corporate_id, store_id):
                raise ManagerAssignmentConflictError(
                    "未完了の処方箋または調剤がある店舗は閉局できません。"
                )
            applied_on = now.astimezone(ZoneInfo("Asia/Tokyo")).date()
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


class ManagerAction(StrEnum):
    """任命履歴への更新分類。"""

    APPOINT = "appoint"
    REPLACE = "replace"
    CANCEL = "cancel"
    END = "end"


@dataclass(frozen=True, kw_only=True)
class ManagerAssignmentDto:
    """任命履歴の公開値。"""

    id: str
    corporate_id: str
    store_id: str
    staff_id: str
    starts_on: date
    ends_on: date | None
    status: str

    @classmethod
    def from_entity(cls, assignment: StoreManagerAssignment) -> ManagerAssignmentDto:
        """集約の期間と参照を公開値へ変換する。"""
        return cls(
            id=str(assignment.id.value),
            corporate_id=str(assignment.corporate_id.value),
            store_id=str(assignment.store_id.value),
            staff_id=str(assignment.staff_id.value),
            starts_on=assignment.period.starts_on,
            ends_on=assignment.period.ends_on,
            status=assignment.status.value,
        )


@dataclass(frozen=True, kw_only=True)
class ManageStoreManagerCommand:
    """任命・交代・取消・終了の入力。"""

    corporate_id: str
    store_id: str
    action: ManagerAction
    assignment_id: str | None = None
    staff_id: str | None = None
    starts_on: date | None = None
    ends_on: date | None = None


class ManageStoreManagerUseCase:
    """任命の期間とスタッフの状態を確認して履歴を更新する。"""

    def __init__(
        self,
        stores: StoreRepository,
        staff: StaffRepository,
        managers: StoreManagerAssignmentRepository,
        access: CorporateAccessBoundary,
        clock: Clock,
        unit_of_work: UnitOfWork,
        lock: OrganizationLock,
    ) -> None:
        self._stores = stores
        self._staff = staff
        self._managers = managers
        self._access = access
        self._clock = clock
        self._unit_of_work = unit_of_work
        self._lock = lock

    async def execute(self, command: ManageStoreManagerCommand) -> ManagerAssignmentDto:
        """同一法人内で期間付き任命を更新する。"""
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
        existing = None
        if command.assignment_id is not None:
            existing = await self._managers.get(
                StoreManagerAssignmentId.parse(command.assignment_id)
            )
            if (
                existing is None
                or existing.corporate_id != corporate_id
                or existing.store_id != store_id
            ):
                raise NotFoundError("指定された任命が見つかりません。")
        today = self._clock.now().astimezone(ZoneInfo("Asia/Tokyo")).date()
        if command.action in {ManagerAction.CANCEL, ManagerAction.END}:
            if existing is None:
                raise DomainValidationError("任命IDを指定してください。")
            if command.action == ManagerAction.CANCEL:
                updated = existing.cancel(applied_on=today)
            else:
                if command.ends_on is None:
                    raise DomainValidationError("任命終了日を指定してください。")
                updated = existing.end(ends_on=command.ends_on)
        else:
            if command.staff_id is None or command.starts_on is None:
                raise DomainValidationError("任命にはスタッフと開始日が必要です。")
            staff = await self._staff.get(
                corporate_id=corporate_id, staff_id=StaffId.parse(command.staff_id)
            )
            if staff is None or staff.corporate_id != corporate_id:
                raise NotFoundError("指定されたスタッフが見つかりません。")
            updated = StoreManagerAssignment(
                id=StoreManagerAssignmentId.generate(),
                corporate_id=corporate_id,
                store_id=store_id,
                staff_id=staff.id,
                period=ManagerAssignmentPeriod(
                    starts_on=command.starts_on, ends_on=command.ends_on
                ),
            )
            StoreManagerAssignmentService().ensure_assignable(
                updated, store=store, staff=staff
            )
            if command.action == ManagerAction.REPLACE:
                if existing is None:
                    raise DomainValidationError("交代元の任命IDを指定してください。")
                await self._managers.save(
                    existing.end(ends_on=command.starts_on - timedelta(days=1))
                )
        await self._managers.save(updated)
        return ManagerAssignmentDto.from_entity(updated)

    async def list_assignments(
        self,
        corporate_id: str,
        store_id: str,
        *,
        as_of: date | None = None,
        after: str | None = None,
        limit: int = 50,
    ) -> dict[str, object]:
        """店舗内の任命履歴、または指定日に有効な任命を返す。"""
        corporate = CorporateId.parse(corporate_id)
        store = StoreId.parse(store_id)
        await self._access.require_active(
            corporate_id=corporate, permission=Permission.VIEW_STORE
        )
        await load_store_or_raise(self._stores, corporate_id=corporate, store_id=store)
        if not 1 <= limit <= 100:
            raise DomainValidationError("件数は1から100で指定してください。")
        after_id = StoreManagerAssignmentId.parse(after) if after else None
        rows = sorted(
            await self._managers.list_by_store(corporate, store),
            key=lambda item: item.id.value,
        )
        rows = [
            item
            for item in rows
            if (as_of is None or item.is_effective_on(as_of))
            and (after_id is None or item.id.value > after_id.value)
        ]
        return {
            "items": [ManagerAssignmentDto.from_entity(item) for item in rows[:limit]],
            "next_cursor": str(rows[limit - 1].id.value) if len(rows) > limit else None,
        }
