"""患者ユースケース用の店舗法人境界Fake。"""

from __future__ import annotations

from app.application.patient.exceptions import PatientStoreNotFoundError
from app.application.patient.reference import PatientStoreReferenceBoundary
from app.domain.corporate.primitives import CorporateId
from app.domain.store.primitives import StoreId
from app.domain.store.repository import StoreRepository


class InMemoryPatientStoreReference(PatientStoreReferenceBoundary):
    """指定店舗が同じ法人に属するかを店舗Repositoryから確認する。"""

    def __init__(self, repository: StoreRepository) -> None:
        self._repository = repository

    async def require_exists(
        self,
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
    ) -> None:
        """未存在・別法人の店舗を404相当へ畳む。"""
        store = await self._repository.get(store_id)
        if store is None or store.corporate_id != corporate_id:
            raise PatientStoreNotFoundError()
