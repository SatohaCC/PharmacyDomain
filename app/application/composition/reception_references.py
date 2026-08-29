"""Receptionの参照境界を店舗・患者Repositoryへ接続する実アダプタ。"""

from __future__ import annotations

from app.application.composition.reference_support import load_store_in_corporate
from app.application.reception.exceptions import (
    ReceptionPatientNotFoundError,
    ReceptionStoreNotFoundError,
)
from app.application.reception.reference import (
    PatientReferenceBoundary,
    StoreReferenceBoundary,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientId
from app.domain.patient.repository import PatientRepository
from app.domain.store.primitives import StoreId
from app.domain.store.repository import StoreRepository


class ReceptionStoreReferenceAdapter(StoreReferenceBoundary):
    """店舗の存在と法人境界だけを確認し、店舗集約は渡さない。"""

    def __init__(self, repository: StoreRepository) -> None:
        self._repository = repository

    async def require_exists(
        self,
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
    ) -> None:
        """未存在・別法人の店舗を、存在を隠す404相当へ畳む。"""
        store = await load_store_in_corporate(
            self._repository,
            corporate_id=corporate_id,
            store_id=store_id,
        )
        if store is None:
            raise ReceptionStoreNotFoundError()


class ReceptionPatientReferenceAdapter(PatientReferenceBoundary):
    """患者の存在と法人境界だけを確認し、患者集約は渡さない。"""

    def __init__(self, repository: PatientRepository) -> None:
        self._repository = repository

    async def require_exists(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
    ) -> None:
        """未存在・別法人の患者を、存在を隠す404相当へ畳む。"""
        patient = await self._repository.get(
            corporate_id=corporate_id,
            patient_id=patient_id,
        )
        if patient is None:
            raise ReceptionPatientNotFoundError()
