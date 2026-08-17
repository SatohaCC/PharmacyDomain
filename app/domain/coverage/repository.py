"""患者資格のリポジトリインターフェース。"""

from __future__ import annotations

from typing import Protocol

from app.domain.corporate.primitives import CorporateId
from app.domain.coverage.patient_coverage import PatientCoverage
from app.domain.coverage.primitives import PatientCoverageId
from app.domain.patient.primitives import PatientId


class PatientCoverageRepository(Protocol):
    """患者資格集約を永続化・検索するための操作インターフェース。"""

    async def get(
        self,
        *,
        corporate_id: CorporateId,
        coverage_id: PatientCoverageId,
    ) -> PatientCoverage | None:
        """指定法人の患者資格を取得する。"""
        ...

    async def list_by_patient(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
    ) -> list[PatientCoverage]:
        """指定法人・患者の患者資格一覧を取得する。"""
        ...

    async def save(self, coverage: PatientCoverage) -> None:
        """患者資格を新規登録または変更保存する。"""
        ...
