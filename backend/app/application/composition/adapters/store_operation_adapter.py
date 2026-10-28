"""Applicationのstore_operation_adapterを定義する。"""

from __future__ import annotations

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.access_control.interfaces.store_operations import (
    MANAGER_REQUIRED_BY_KIND,
    STORE_OPERATION_KINDS,
    StoreOperation,
    StoreOperationBoundary,
    StoreOperationKind,
)
from app.application.common.clock import Clock, business_date
from app.application.store.errors import StoreNotFoundError
from app.domain.corporate.identifiers import CorporateId
from app.domain.store.exceptions import (
    ManagerAbsenceConflictError,
    StoreStateConflictError,
)
from app.domain.store.identifiers import StoreId
from app.domain.store.primitives import StoreStatus
from app.domain.store.repositories import (
    StoreManagerAssignmentRepository,
    StoreRepository,
)


class StoreOperationAdapter(StoreOperationBoundary):
    """存在確認・店舗状態・管理薬剤師の在任を区別して拒否する。"""

    def __init__(
        self,
        repository: StoreRepository,
        corporate_access: CorporateAccessBoundary,
        managers: StoreManagerAssignmentRepository,
        clock: Clock,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access
        self._managers = managers
        self._clock = clock

    async def require_allowed(
        self, *, corporate_id: CorporateId, store_id: StoreId, operation: StoreOperation
    ) -> None:
        """店舗の現在状態と管理薬剤師の在任に対して操作を検証する。"""
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.VIEW_STORE
        )
        store = await self._repository.get(store_id)
        if store is None or store.corporate_id != corporate_id:
            raise StoreNotFoundError()
        kind = STORE_OPERATION_KINDS[operation]
        if (
            kind is StoreOperationKind.NEW_WORK
            and store.status != StoreStatus.ACTIVE
            or (
                kind is StoreOperationKind.CONTINUING
                and store.status == StoreStatus.CLOSED
            )
        ):
            raise StoreStateConflictError(
                "現在の店舗状態ではこの操作を実行できません。"
            )
        if not MANAGER_REQUIRED_BY_KIND[kind]:
            return
        assignment = await self._managers.find_effective(
            corporate_id, store_id, business_date(self._clock)
        )
        if assignment is None:
            raise ManagerAbsenceConflictError(
                "管理薬剤師が在任していない店舗では、新しい業務を開始できません。"
            )
