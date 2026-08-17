"""適用資格利用履歴を記録するユースケース。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.application.access_control import CorporateAccessBoundary, Permission
from app.application.claim.get_coverage_usage import CoverageUsageDto
from app.application.claim.reference import (
    CoverageSnapshotBoundary,
    PatientReferenceBoundary,
    StoreReferenceBoundary,
)
from app.domain.claim import (
    CoverageUsage,
    CoverageUsageRepository,
    CoverageUsageTimestamp,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientId
from app.domain.store.primitives import StoreId


@dataclass(frozen=True, kw_only=True)
class RecordCoverageUsageCommand:
    """適用資格利用履歴登録の入力データ。"""

    corporate_id: str
    store_id: str
    patient_id: str
    applied_at: datetime
    coverage_ids: tuple[str, ...]


class RecordCoverageUsageUseCase:
    """選択された資格をスナップショット化して利用履歴へ保存する。"""

    def __init__(
        self,
        repository: CoverageUsageRepository,
        corporate_access: CorporateAccessBoundary,
        store_reference: StoreReferenceBoundary,
        patient_reference: PatientReferenceBoundary,
        coverage_snapshot: CoverageSnapshotBoundary,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access
        self._store_reference = store_reference
        self._patient_reference = patient_reference
        self._coverage_snapshot = coverage_snapshot

    async def execute(
        self,
        command: RecordCoverageUsageCommand,
    ) -> CoverageUsageDto:
        """法人・店舗・患者の境界を確認して利用履歴を保存する。"""
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.MANAGE_COVERAGE,
        )
        store_id = StoreId.parse(command.store_id)
        await self._store_reference.require_exists(
            corporate_id=corporate_id,
            store_id=store_id,
        )
        patient_id = PatientId.parse(command.patient_id)
        await self._patient_reference.require_exists(
            corporate_id=corporate_id,
            patient_id=patient_id,
        )
        applied_at = CoverageUsageTimestamp(command.applied_at)
        snapshot = await self._coverage_snapshot.build_snapshot(
            corporate_id=corporate_id,
            patient_id=patient_id,
            coverage_ids=command.coverage_ids,
            applied_at=applied_at,
        )
        usage = CoverageUsage.create(
            corporate_id=corporate_id,
            store_id=store_id,
            patient_id=patient_id,
            applied_at=applied_at,
            snapshot=snapshot,
        )
        await self._repository.save(usage)
        return CoverageUsageDto.from_entity(usage)
