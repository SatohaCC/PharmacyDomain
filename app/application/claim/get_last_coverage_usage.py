"""最後に使用した適用資格を取得するユースケース。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control import CorporateAccessBoundary, Permission
from app.application.claim.get_coverage_usage import CoverageUsageDto
from app.application.claim.reference import (
    PatientReferenceBoundary,
    StoreReferenceBoundary,
)
from app.domain.claim.repository import CoverageUsageRepository
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientId
from app.domain.store.primitives import StoreId


@dataclass(frozen=True, kw_only=True)
class GetLastCoverageUsageQuery:
    """最後に使用した適用資格取得の入力データ。"""

    corporate_id: str
    store_id: str
    patient_id: str


class GetLastCoverageUsageUseCase:
    """法人・店舗・患者単位で最後に使用した資格を候補として返す。"""

    def __init__(
        self,
        repository: CoverageUsageRepository,
        corporate_access: CorporateAccessBoundary,
        store_reference: StoreReferenceBoundary,
        patient_reference: PatientReferenceBoundary,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access
        self._store_reference = store_reference
        self._patient_reference = patient_reference

    async def execute(
        self,
        query: GetLastCoverageUsageQuery,
    ) -> CoverageUsageDto | None:
        """対象境界を確認し、最新履歴があれば候補DTOを返す。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.VIEW_COVERAGE,
        )
        store_id = StoreId.parse(query.store_id)
        await self._store_reference.require_exists(
            corporate_id=corporate_id,
            store_id=store_id,
        )
        patient_id = PatientId.parse(query.patient_id)
        await self._patient_reference.require_exists(
            corporate_id=corporate_id,
            patient_id=patient_id,
        )
        usage = await self._repository.get_latest(
            corporate_id=corporate_id,
            store_id=store_id,
            patient_id=patient_id,
        )
        return CoverageUsageDto.from_entity(usage) if usage is not None else None
