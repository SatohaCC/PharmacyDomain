"""最後に使用した適用資格を保存する利用履歴集約。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Self

from app.base.domain.entity import AggregateRoot
from app.domain.claim.coverage_snapshot import CoverageSnapshot
from app.domain.claim.primitives import ClaimCoverageUsageId, CoverageUsageTimestamp
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientId
from app.domain.store.primitives import StoreId


@dataclass(frozen=True, eq=False, kw_only=True)
class CoverageUsage(AggregateRoot[ClaimCoverageUsageId]):
    """患者・店舗単位で適用資格の利用履歴を保持する集約ルート。"""

    id: ClaimCoverageUsageId
    corporate_id: CorporateId
    store_id: StoreId
    patient_id: PatientId
    applied_at: CoverageUsageTimestamp
    snapshot: CoverageSnapshot

    @classmethod
    def create(
        cls,
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
        patient_id: PatientId,
        applied_at: CoverageUsageTimestamp,
        snapshot: CoverageSnapshot,
    ) -> Self:
        """適用資格利用履歴を生成する。"""
        return cls(
            id=ClaimCoverageUsageId.generate(),
            corporate_id=corporate_id,
            store_id=store_id,
            patient_id=patient_id,
            applied_at=applied_at,
            snapshot=snapshot,
        )
