"""Applicationのmanage_store_managerを定義する。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.common.clock import Clock, business_date
from app.application.common.exceptions import NotFoundError
from app.application.common.organization_lock import OrganizationLock
from app.application.common.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, Page
from app.application.common.unit_of_work import UnitOfWork
from app.application.store.commands.dtos.management import ManagerAssignmentDto
from app.application.store.commands.models import ManagerAction
from app.application.store.commands.services.support import load_store_or_raise
from app.application.store.interfaces.management import StaffPersonBoundary
from app.application.store.interfaces.references import ManagerStaffReference
from app.domain.corporate.identifiers import CorporateId
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.staff.identifiers import StaffId
from app.domain.store.entities import StoreManagerAssignment
from app.domain.store.exceptions import ManagerPersonUnresolvedError
from app.domain.store.identifiers import StoreId, StoreManagerAssignmentId
from app.domain.store.repositories import (
    StoreManagerAssignmentRepository,
    StoreRepository,
)
from app.domain.store.services import StoreManagerAssignmentService
from app.domain.store.value_objects import ManagerAssignmentPeriod


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
        staff: ManagerStaffReference,
        managers: StoreManagerAssignmentRepository,
        people: StaffPersonBoundary,
        access: CorporateAccessBoundary,
        clock: Clock,
        unit_of_work: UnitOfWork,
        lock: OrganizationLock,
    ) -> None:
        self._stores = stores
        self._staff = staff
        self._managers = managers
        self._people = people
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
        today = business_date(self._clock)
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
            person_id = await self._people.person_of(corporate_id, staff.staff_id)
            if person_id is None:
                raise ManagerPersonUnresolvedError(
                    "管理薬剤師に任命するには、スタッフと本人の対応が必要です。"
                )
            updated = StoreManagerAssignment(
                id=StoreManagerAssignmentId.generate(),
                corporate_id=corporate_id,
                store_id=store_id,
                staff_id=staff.staff_id,
                person_id=person_id,
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
        limit: int = DEFAULT_PAGE_SIZE,
    ) -> Page[ManagerAssignmentDto]:
        """店舗内の任命履歴、または指定日に有効な任命を返す。"""
        corporate = CorporateId.parse(corporate_id)
        store = StoreId.parse(store_id)
        await self._access.require_active(
            corporate_id=corporate, permission=Permission.VIEW_STORE
        )
        await load_store_or_raise(self._stores, corporate_id=corporate, store_id=store)
        if not 1 <= limit <= MAX_PAGE_SIZE:
            raise DomainValidationError(
                f"件数は1から{MAX_PAGE_SIZE}で指定してください。"
            )
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
        page = rows[:limit]
        return Page(
            items=tuple(ManagerAssignmentDto.from_entity(item) for item in page),
            next_cursor=str(page[-1].id.value) if len(rows) > limit else None,
        )
