"""Applicationのclinical_store_guardを定義する。"""

from __future__ import annotations

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.store_operations import (
    StoreOperation,
    StoreOperationBoundary,
)
from app.application.access_control.policies import AuthorizationService
from app.application.common.organization_lock import OrganizationLock
from app.domain.care_event.entities import Event
from app.domain.coverage.entities import CoverageSelectionRecord
from app.domain.dispensing.entities import DispensingProcess
from app.domain.medication_history.entities import MedicationHistoryRecord
from app.domain.prescription.entities import Prescription


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
        elif isinstance(aggregate, Event):
            permission = Permission.MANAGE_EVENT
            operation = StoreOperation.CREATE_EVENT
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
