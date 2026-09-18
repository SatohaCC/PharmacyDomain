"""臨床集約の保存を実際の店舗へ結び付ける境界。"""

from app.application.access_control.models import Permission
from app.application.access_control.policy import AuthorizationService
from app.application.access_control.store_access import (
    StoreOperation,
    StoreOperationBoundary,
)
from app.application.common.organization_lock import OrganizationLock
from app.domain.dispensing.dispensing_process import DispensingProcess
from app.domain.medication_history.medication_history_record import (
    MedicationHistoryRecord,
)
from app.domain.prescription.prescription import Prescription
from app.domain.reception.coverage_selection_record import CoverageSelectionRecord


class ClinicalStoreWriteGuard:
    """保存する集約が持つ店舗で権限と現在状態を検証する。"""

    def __init__(
        self,
        stores: StoreOperationBoundary,
        authorization: AuthorizationService,
        lock: OrganizationLock,
    ) -> None:
        self._stores = stores
        self._authorization = authorization
        self._lock = lock

    async def check(self, aggregate: object, is_new: bool) -> None:
        """HTTPの店舗指定ではなく保存対象の店舗へ検証を適用する。"""
        if isinstance(aggregate, Prescription):
            permission = Permission.MANAGE_PRESCRIPTION
            operation = (
                StoreOperation.REGISTER_PRESCRIPTION
                if is_new
                else StoreOperation.RECORD_DISPENSING
            )
        elif isinstance(aggregate, DispensingProcess):
            permission = Permission.MANAGE_DISPENSING
            operation = (
                StoreOperation.START_DISPENSING
                if is_new
                else StoreOperation.RECORD_DISPENSING
            )
        elif isinstance(aggregate, CoverageSelectionRecord):
            permission = Permission.MANAGE_RECEPTION
            operation = StoreOperation.RECORD_RECEPTION
        elif isinstance(aggregate, MedicationHistoryRecord):
            permission = Permission.MANAGE_MEDICATION_HISTORY
            operation = (
                StoreOperation.START_HISTORY if is_new else StoreOperation.AMEND_HISTORY
            )
        else:
            return
        # 法人をまたぐ不変条件は無いので、法人ごとの直列化で足りる。以前は
        # "identity" の単一キーも取っており、無関係な法人どうしの調剤が
        # 互いをブロックしていた。
        await self._lock.acquire(f"corporate:{aggregate.corporate_id.value}")
        self._authorization.require_store(
            permission=permission,
            target_corporate_id=aggregate.corporate_id,
            target_store_id=aggregate.store_id,
        )
        await self._stores.require_allowed(
            corporate_id=aggregate.corporate_id,
            store_id=aggregate.store_id,
            operation=operation,
        )
