"""適用資格利用履歴Repositoryのインメモリ実装。"""

from __future__ import annotations

import copy

from app.domain.claim.coverage_usage import CoverageUsage
from app.domain.claim.repository import CoverageUsageRepository
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientId
from app.domain.store.primitives import StoreId


class InMemoryCoverageUsageRepository(CoverageUsageRepository):
    """法人・店舗・患者境界と最新日時を扱うテスト用Repository。"""

    def __init__(self) -> None:
        self.items: dict[str, CoverageUsage] = {}

    async def save(self, usage: CoverageUsage) -> None:
        """利用履歴をコピーして保存する。"""
        self.items[str(usage.id.value)] = copy.deepcopy(usage)

    async def get_latest(
        self,
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
        patient_id: PatientId,
    ) -> CoverageUsage | None:
        """指定スコープの利用履歴から適用日時が最新のものを返す。"""
        candidates = [
            item
            for item in self.items.values()
            if item.corporate_id == corporate_id
            and item.store_id == store_id
            and item.patient_id == patient_id
        ]
        if not candidates:
            return None
        latest = max(candidates, key=lambda item: item.applied_at.value)
        return copy.deepcopy(latest)
