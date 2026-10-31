"""Applicationのstore_operation_adapterを定義する。"""

from __future__ import annotations

from datetime import date

from app.application.access_control.boundary_models import (
    ActorRole,
    Permission,
    ResolvedActorContext,
)
from app.application.access_control.errors import (
    StoreContextRequiredError,
    TenantBoundaryNotFoundError,
)
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
    NarcoticsLicenseRequiredConflictError,
    PharmacyLicenseRequiredConflictError,
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
        self,
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
        operation: StoreOperation,
        has_narcotics: bool = False,
        business_on: date | None = None,
    ) -> None:
        """店舗の現在状態と管理薬剤師の在任に対して操作を検証する。"""
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.VIEW_STORE
        )
        actor = self._corporate_access.actor
        if (
            isinstance(actor, ResolvedActorContext)
            and ActorRole.VENDOR_SYSTEM_ADMIN not in actor.roles
        ):
            if actor.corporate_id != corporate_id:
                raise TenantBoundaryNotFoundError()
            if actor.require_store_selection and actor.selected_store_id is None:
                raise StoreContextRequiredError()
            if (
                actor.selected_store_id is not None
                and store_id != actor.selected_store_id
            ):
                raise TenantBoundaryNotFoundError()
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
        today = business_on if business_on is not None else business_date(self._clock)
        if MANAGER_REQUIRED_BY_KIND[kind]:
            assignment = await self._managers.find_effective(
                corporate_id, store_id, today
            )
            if assignment is None:
                raise ManagerAbsenceConflictError(
                    "管理薬剤師が在任していない店舗では、新しい業務を開始できません。"
                )
        if kind in (StoreOperationKind.NEW_WORK, StoreOperationKind.CONTINUING):
            if (
                store.licenses is None
                or store.licenses.pharmacy_license is None
                or not store.licenses.pharmacy_license.is_effective_on(today)
            ):
                raise PharmacyLicenseRequiredConflictError(
                    "店舗の薬局開設許可が登録されていないか有効期間外のため、この操作を実行できません。"
                )
            if has_narcotics and (
                store.licenses is None
                or store.licenses.narcotics_retailer_license is None
                or not store.licenses.narcotics_retailer_license.is_effective_on(today)
            ):
                raise NarcoticsLicenseRequiredConflictError(
                    "麻薬小売業者免許が登録されていないか有効期間外のため、麻薬に関する操作を実行できません。"
                )
