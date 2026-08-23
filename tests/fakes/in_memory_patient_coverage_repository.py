"""患者資格Repositoryのインメモリ実装。"""

from __future__ import annotations

import copy

from app.domain.corporate.primitives import CorporateId
from app.domain.coverage.patient_coverage import PatientCoverage
from app.domain.coverage.primitives import PatientCoverageId
from app.domain.coverage.repository import PatientCoverageRepository
from app.domain.coverage.services import PatientCoverageConflictService
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
        """実効期間の競合を原子的に拒否して資格を保存する。

        Applicationの事前readは早期エラー用であり原子性の代替ではないため、
        Repository契約として保存の直前にも同じ判定を行う。同じ集約IDの現在行は
        競合候補から除外し、自身の期間変更や無効化を妨げない。
        """
        PatientCoverageConflictService().ensure_no_conflict(
            coverage,
            [item for item in self.items.values() if item.id != coverage.id],
        )
        self.items[coverage.id] = copy.deepcopy(coverage)
