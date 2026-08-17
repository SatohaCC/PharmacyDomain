"""患者資格Repositoryのインメモリ実装。"""

from __future__ import annotations

import copy

from app.domain.corporate.primitives import CorporateId
from app.domain.coverage.patient_coverage import PatientCoverage
from app.domain.coverage.primitives import PatientCoverageId
from app.domain.coverage.repository import PatientCoverageRepository
from app.domain.patient.primitives import PatientId


class InMemoryPatientCoverageRepository(PatientCoverageRepository):
    """法人・患者境界を適用するテスト用患者資格Repository。"""

    def __init__(self) -> None:
        self.items: dict[PatientCoverageId, PatientCoverage] = {}

    async def get(
        self,
        *,
        corporate_id: CorporateId,
        coverage_id: PatientCoverageId,
    ) -> PatientCoverage | None:
        """指定法人の資格だけを取得する。"""
        item = self.items.get(coverage_id)
        if item is None or item.corporate_id != corporate_id:
            return None
        return copy.deepcopy(item)

    async def list_by_patient(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
    ) -> list[PatientCoverage]:
        """指定法人・患者の資格だけを一覧する。"""
        return [
            copy.deepcopy(item)
            for item in self.items.values()
            if item.corporate_id == corporate_id and item.patient_id == patient_id
        ]

    async def save(self, coverage: PatientCoverage) -> None:
        """資格をコピーして保存する。"""
        self.items[coverage.id] = copy.deepcopy(coverage)
