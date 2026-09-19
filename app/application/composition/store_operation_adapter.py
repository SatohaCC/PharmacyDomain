"""店舗の操作境界を法人確認と店舗Repositoryへ接続する。"""

from app.application.access_control import CorporateAccessBoundary, Permission
from app.application.access_control.store_access import (
    STORE_OPERATION_KINDS,
    StoreOperation,
    StoreOperationBoundary,
    StoreOperationKind,
)
from app.application.store.exceptions import StoreNotFoundError
from app.domain.corporate.primitives import CorporateId
from app.domain.store.lifecycle import StoreStateConflictError, StoreStatus
from app.domain.store.primitives import StoreId
from app.domain.store.repository import StoreRepository


class StoreOperationAdapter(StoreOperationBoundary):
    """存在確認と新規業務可能性を区別する。"""

    def __init__(
        self, repository: StoreRepository, corporate_access: CorporateAccessBoundary
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access

    async def require_allowed(
        self, *, corporate_id: CorporateId, store_id: StoreId, operation: StoreOperation
    ) -> None:
        """店舗の現在状態に対して操作を検証する。"""
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
