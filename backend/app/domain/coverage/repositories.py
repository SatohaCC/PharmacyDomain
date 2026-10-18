"""coverageの保存・情報取得の抽象契約。"""

from __future__ import annotations

from typing import Protocol

from app.domain.corporate.identifiers import CorporateId
from app.domain.coverage.entities import CoverageSelectionRecord, PatientCoverage
from app.domain.coverage.identifiers import CoverageSelectionRecordId, PatientCoverageId
from app.domain.patient.identifiers import PatientId
from app.domain.store.identifiers import StoreId


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
        """実効期間の競合を原子的に拒否して患者資格を保存する。"""
        ...


class CoverageSelectionRecordRepository(Protocol):
    """適用資格選択履歴を保存・検索するための操作。"""

    async def save(self, record: CoverageSelectionRecord) -> None:
        """履歴を新規保存する。複数履歴を許可し、一意性制約は課さない。"""
        ...

    async def get(
        self,
        *,
        corporate_id: CorporateId,
        record_id: CoverageSelectionRecordId,
    ) -> CoverageSelectionRecord | None:
        """指定法人の履歴をIDで取得する。"""
        ...

    async def get_latest(
        self,
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
        patient_id: PatientId,
    ) -> CoverageSelectionRecord | None:
        """``(recorded_at, id)`` の降順で最新の履歴を取得する。"""
        ...
