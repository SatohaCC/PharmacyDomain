"""最後に使用した適用資格を取得するユースケース。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.application.access_control import CorporateAccessBoundary, Permission
from app.application.claim.get_coverage_usage import CoverageUsageDto
from app.application.claim.reference import (
    CoverageValidityBoundary,
    PatientReferenceBoundary,
    StoreReferenceBoundary,
)
from app.domain.claim.repository import CoverageUsageRepository
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientId
from app.domain.store.primitives import StoreId


@dataclass(frozen=True, kw_only=True)
class GetLastCoverageUsageQuery:
    """最後に使用した適用資格取得の入力データ。

    ``applied_on`` は今回の調剤・請求の適用日。最新履歴は初期候補にすぎないため、
    どの日付で再検証するかを呼び出し元が必ず明示する。
    """

    corporate_id: str
    store_id: str
    patient_id: str
    applied_on: date


@dataclass(frozen=True, kw_only=True)
class LastCoverageUsageCandidateDto:
    """初期候補として返す最新履歴と、その適用日時点での有効性。

    ``is_still_valid`` が ``False`` の候補を自動適用してはならない。呼び出し元が
    有効・無効を区別できるようフラグとして明示し、「候補は適用日で再検証し、
    資格が無効なら自動適用しない」という規則を型の上で表す。
    """

    usage: CoverageUsageDto
    is_still_valid: bool


class GetLastCoverageUsageUseCase:
    """法人・店舗・患者単位で最後に使用した資格を候補として返す。"""

    def __init__(
        self,
        repository: CoverageUsageRepository,
        corporate_access: CorporateAccessBoundary,
        store_reference: StoreReferenceBoundary,
        patient_reference: PatientReferenceBoundary,
        coverage_validity: CoverageValidityBoundary,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access
        self._store_reference = store_reference
        self._patient_reference = patient_reference
        self._coverage_validity = coverage_validity

    async def execute(
        self,
        query: GetLastCoverageUsageQuery,
    ) -> LastCoverageUsageCandidateDto | None:
        """対象境界を確認し、最新履歴があれば適用日で再検証した候補を返す。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.VIEW_CLAIM,
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
        if usage is None:
            return None
        is_still_valid = await self._coverage_validity.is_snapshot_valid(
            corporate_id=corporate_id,
            patient_id=patient_id,
            snapshot=usage.snapshot,
            applied_on=query.applied_on,
        )
        return LastCoverageUsageCandidateDto(
            usage=CoverageUsageDto.from_entity(usage),
            is_still_valid=is_still_valid,
        )
