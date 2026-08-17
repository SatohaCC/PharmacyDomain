"""適用資格利用履歴のリポジトリインターフェース。"""

from __future__ import annotations

from typing import Protocol

from app.domain.claim.coverage_usage import CoverageUsage
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientId
from app.domain.store.primitives import StoreId


class CoverageUsageRepository(Protocol):
    """適用資格利用履歴を永続化・検索するための操作。"""

    async def save(self, usage: CoverageUsage) -> None:
        """適用資格利用履歴を新規保存する。"""
        ...

    async def get_latest(
        self,
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
        patient_id: PatientId,
    ) -> CoverageUsage | None:
        """法人・店舗・患者単位で最後に使用した履歴を取得する。"""
        ...
