"""Applicationのmanage_safety_managerを定義する。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.store.commands.services.support import load_store_or_raise
from app.application.store.interfaces.references import ManagerStaffReference
from app.domain.corporate.identifiers import CorporateId
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.staff.identifiers import StaffId
from app.domain.store.identifiers import StoreId
from app.domain.store.repositories import StoreRepository


@dataclass(frozen=True, kw_only=True)
class AppointSafetyManagerCommand:
    """医薬品安全管理責任者任命コマンド。"""

    corporate_id: str
    store_id: str
    staff_id: str


@dataclass(frozen=True, kw_only=True)
class RemoveSafetyManagerCommand:
    """医薬品安全管理責任者解任コマンド。"""

    corporate_id: str
    store_id: str


class AppointSafetyManagerUseCase:
    """医薬品安全管理責任者任命ユースケース。"""

    def __init__(
        self,
        repository: StoreRepository,
        staff_reference: ManagerStaffReference,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._repository = repository
        self._staff_reference = staff_reference
        self._corporate_access = corporate_access

    async def execute(self, command: AppointSafetyManagerCommand) -> None:
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.MANAGE_STORE
        )
        store_id = StoreId.parse(command.store_id)
        store = await load_store_or_raise(
            self._repository, corporate_id=corporate_id, store_id=store_id
        )

        staff_id = StaffId.parse(command.staff_id)
        staff_source = await self._staff_reference.get(
            corporate_id=corporate_id, staff_id=staff_id
        )
        if staff_source is None:
            raise DomainValidationError(
                f"指定されたスタッフ（ID: {command.staff_id}）が見つかりません。"
            )
        if not staff_source.staff_is_active:
            raise DomainValidationError(
                "非稼働中のスタッフを医薬品安全管理責任者に任命することはできません。"
            )

        updated = store.appoint_safety_manager(staff_id)
        await self._repository.save(updated)


class RemoveSafetyManagerUseCase:
    """医薬品安全管理責任者解任ユースケース。"""

    def __init__(
        self,
        repository: StoreRepository,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access

    async def execute(self, command: RemoveSafetyManagerCommand) -> None:
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.MANAGE_STORE
        )
        store_id = StoreId.parse(command.store_id)
        store = await load_store_or_raise(
            self._repository, corporate_id=corporate_id, store_id=store_id
        )

        updated = store.remove_safety_manager()
        await self._repository.save(updated)
