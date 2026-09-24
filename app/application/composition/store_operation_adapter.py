"""店舗の操作境界を法人確認・店舗Repository・管理薬剤師の任命へ接続する。"""

from app.application.access_control.boundary import CorporateAccessBoundary
from app.application.access_control.models import Permission
from app.application.access_control.store_access import (
    MANAGER_REQUIRED_BY_KIND,
    STORE_OPERATION_KINDS,
    StoreOperation,
    StoreOperationBoundary,
    StoreOperationKind,
)
from app.application.common.clock import Clock, business_date
from app.application.store.exceptions import StoreNotFoundError
from app.domain.corporate.primitives import CorporateId
from app.domain.store.lifecycle import StoreStateConflictError, StoreStatus
from app.domain.store.manager_assignment import ManagerAbsenceConflictError
from app.domain.store.manager_repository import StoreManagerAssignmentRepository
from app.domain.store.primitives import StoreId
from app.domain.store.repository import StoreRepository


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
            kind is StoreOperationKind.NEW_WORK and store.status != StoreStatus.ACTIVE
        ) or (
            kind is StoreOperationKind.CONTINUING and store.status == StoreStatus.CLOSED
        ):
            raise StoreStateConflictError(
                "現在の店舗状態ではこの操作を実行できません。"
            )
        if not MANAGER_REQUIRED_BY_KIND[kind]:
            return
        # 在任は日付で変わるので、任命を「今」ではなく業務日で引く。判定を
        # 省いて通すのではなく、判定できない状態を拒否へ倒す（在任が確認でき
        # ないまま新しい調剤が始まるほうが、業務が止まるより害が大きい）。
        assignment = await self._managers.find_effective(
            corporate_id, store_id, business_date(self._clock)
        )
        if assignment is None:
            raise ManagerAbsenceConflictError(
                "管理薬剤師が在任していない店舗では、新しい業務を開始できません。"
            )
