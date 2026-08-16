"""兼務店舗解除ユースケース。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.application.access_control import (
    CorporateAccessBoundary,
    Permission,
)
from app.application.staff.support import load_staff_or_raise, load_store_or_raise
from app.domain.corporate.primitives import CorporateId
from app.domain.staff import StaffId, StaffRepository, StaffStoreAssignmentService
from app.domain.store import StoreId, StoreRepository


@dataclass(frozen=True, kw_only=True)
class RemoveStaffConcurrentStoreCommand:
    """兼務店舗解除に必要な入力データ（DTO）。"""

    corporate_id: str
    staff_id: str
    store_id: str
    end_date: date


class RemoveStaffConcurrentStoreUseCase:
    """兼務店舗解除ユースケース。"""

    def __init__(
        self,
        staff_repository: StaffRepository,
        store_repository: StoreRepository,
        assignment_service: StaffStoreAssignmentService,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._staff_repository = staff_repository
        self._store_repository = store_repository
        self._assignment_service = assignment_service
        self._corporate_access = corporate_access

    async def execute(self, command: RemoveStaffConcurrentStoreCommand) -> None:
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.MANAGE_STAFF,
        )
        staff_id = StaffId.parse(command.staff_id)
        store_id = StoreId.parse(command.store_id)

        staff = await load_staff_or_raise(
            self._staff_repository,
            corporate_id=corporate_id,
            staff_id=staff_id,
        )
        store = await load_store_or_raise(
            self._store_repository,
            corporate_id=corporate_id,
            store_id=store_id,
        )

        updated_staff = self._assignment_service.remove_concurrent_store(
            staff,
            store,
            command.end_date,
        )

        await self._staff_repository.save(updated_staff)
