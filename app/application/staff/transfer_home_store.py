"""スタッフの主所属店舗異動ユースケース。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.application.access_control.boundary import CorporateAccessBoundary
from app.application.access_control.models import Permission
from app.application.staff.support import load_staff_or_raise, load_store_or_raise
from app.domain.corporate.primitives import CorporateId
from app.domain.staff.primitives import StaffId
from app.domain.staff.repository import StaffRepository
from app.domain.staff.services import StaffStoreAssignmentService
from app.domain.store.primitives import StoreId
from app.domain.store.repository import StoreRepository


@dataclass(frozen=True, kw_only=True)
class TransferStaffHomeStoreCommand:
    """主所属店舗異動に必要な入力データ（DTO）。"""

    corporate_id: str
    staff_id: str
    new_store_id: str
    transfer_date: date


class TransferStaffHomeStoreUseCase:
    """主所属店舗異動ユースケース。"""

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

    async def execute(self, command: TransferStaffHomeStoreCommand) -> None:
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.MANAGE_STAFF,
        )
        staff_id = StaffId.parse(command.staff_id)
        new_store_id = StoreId.parse(command.new_store_id)

        staff = await load_staff_or_raise(
            self._staff_repository,
            corporate_id=corporate_id,
            staff_id=staff_id,
        )
        store = await load_store_or_raise(
            self._store_repository,
            corporate_id=corporate_id,
            store_id=new_store_id,
        )

        updated_staff = self._assignment_service.transfer_home_store(
            staff,
            store,
            command.transfer_date,
        )

        await self._staff_repository.save(updated_staff)
