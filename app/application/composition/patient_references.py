"""Patientの外部Repository参照Boundary実装。"""

from __future__ import annotations

from app.application.composition.reference_support import load_store_in_corporate
from app.application.patient.exceptions import PatientStoreNotFoundError
from app.application.patient.reference import PatientStoreReferenceBoundary
from app.domain.corporate.primitives import CorporateId
from app.domain.store.primitives import StoreId
from app.domain.store.repository import StoreRepository


class PatientStoreReferenceAdapter(PatientStoreReferenceBoundary):
    """店舗集約を保持せず、患者外部ID登録時の法人境界を確認する。"""

    def __init__(self, repository: StoreRepository) -> None:
        self._repository = repository

    async def require_exists(
        self,
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
    ) -> None:
        """未存在・別法人の店舗を404相当へ畳む。"""
        store = await load_store_in_corporate(
            self._repository,
            corporate_id=corporate_id,
            store_id=store_id,
        )
        if store is None:
            raise PatientStoreNotFoundError()
