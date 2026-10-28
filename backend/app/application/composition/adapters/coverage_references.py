"""Applicationのcoverage_referencesを定義する。"""

from __future__ import annotations

from app.application.composition.adapters.reference_support import (
    load_store_in_corporate,
)
from app.application.coverage.errors import (
    CoveragePatientNotFoundError,
    CoverageStoreNotFoundError,
)
from app.application.coverage.interfaces.references import (
    PatientReferenceBoundary,
    StoreReferenceBoundary,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.patient.identifiers import PatientId
from app.domain.patient.repositories import PatientRepository
from app.domain.store.identifiers import StoreId
from app.domain.store.repositories import StoreRepository


class CoveragePatientReferenceAdapter(PatientReferenceBoundary):
    """患者の存在と法人境界だけを確認し、患者集約は渡さない。"""

    def __init__(self, repository: PatientRepository) -> None:
        self._repository = repository

    async def require_exists(
        self, *, corporate_id: CorporateId, patient_id: PatientId
    ) -> None:
        """未存在・別法人の患者を、存在を隠す404相当へ畳む。

        ``PatientRepository.get()`` が他法人の患者へ ``None`` を返す契約なので、
        法人境界の判定はRepositoryに委ねられる。
        """
        patient = await self._repository.get(
            corporate_id=corporate_id, patient_id=patient_id
        )
        if patient is None:
            raise CoveragePatientNotFoundError()


class CoverageStoreReferenceAdapter(StoreReferenceBoundary):
    """店舗の存在と法人境界だけを確認し、店舗集約は渡さない。"""

    def __init__(self, repository: StoreRepository) -> None:
        self._repository = repository

    async def require_exists(
        self, *, corporate_id: CorporateId, store_id: StoreId
    ) -> None:
        """未存在・別法人の店舗を、存在を隠す404相当へ畳む。"""
        store = await load_store_in_corporate(
            self._repository, corporate_id=corporate_id, store_id=store_id
        )
        if store is None:
            raise CoverageStoreNotFoundError()
