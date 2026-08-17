"""Claim Applicationが依存する参照境界のフェイク実装。

各Protocolの ``Raises:`` に書かれた契約（他テナントのデータは403ではなく404相当の
例外で隠蔽する）を実行可能な形で表す。Composition Rootに置かれる本実装も同じ
契約を満たす必要がある。
"""

from __future__ import annotations

from datetime import date

from app.application.claim.exceptions import (
    ClaimCoverageSelectionError,
    ClaimPatientNotFoundError,
    ClaimStoreNotFoundError,
)
from app.application.claim.reference import (
    CoverageSnapshotBoundary,
    CoverageValidityBoundary,
    PatientReferenceBoundary,
    StoreReferenceBoundary,
)
from app.domain.claim.coverage_snapshot import CoverageSnapshot
from app.domain.claim.primitives import CoverageUsageTimestamp
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientId
from app.domain.store.primitives import StoreId


class FakeStoreReference(StoreReferenceBoundary):
    """法人ごとに登録された店舗IDだけを存在として扱う境界。"""

    def __init__(self) -> None:
        self.registered: set[tuple[CorporateId, StoreId]] = set()

    def register(self, *, corporate_id: CorporateId, store_id: StoreId) -> None:
        """指定法人に店舗を存在させる。"""
        self.registered.add((corporate_id, store_id))

    async def require_exists(
        self,
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
    ) -> None:
        """店舗が存在しない、または別法人の場合は404相当を送出する。"""
        if (corporate_id, store_id) not in self.registered:
            raise ClaimStoreNotFoundError()


class FakePatientReference(PatientReferenceBoundary):
    """法人ごとに登録された患者IDだけを存在として扱う境界。"""

    def __init__(self) -> None:
        self.registered: set[tuple[CorporateId, PatientId]] = set()

    def register(self, *, corporate_id: CorporateId, patient_id: PatientId) -> None:
        """指定法人に患者を存在させる。"""
        self.registered.add((corporate_id, patient_id))

    async def require_exists(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
    ) -> None:
        """患者が存在しない、または別法人の場合は404相当を送出する。"""
        if (corporate_id, patient_id) not in self.registered:
            raise ClaimPatientNotFoundError()


class FakeCoverageSnapshotSource(CoverageSnapshotBoundary):
    """資格IDの組に対して用意されたスナップショットを返す境界。"""

    def __init__(self) -> None:
        self.snapshots: dict[tuple[str, ...], CoverageSnapshot] = {}

    def register(
        self,
        *,
        coverage_ids: tuple[str, ...],
        snapshot: CoverageSnapshot,
    ) -> None:
        """資格IDの組に対応するスナップショットを登録する。"""
        self.snapshots[coverage_ids] = snapshot

    async def build_snapshot(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
        coverage_ids: tuple[str, ...],
        applied_at: CoverageUsageTimestamp,
    ) -> CoverageSnapshot:
        """登録のない資格IDの組は選択エラーとして扱う。"""
        del corporate_id, patient_id, applied_at
        snapshot = self.snapshots.get(coverage_ids)
        if snapshot is None:
            raise ClaimCoverageSelectionError()
        return snapshot


class FakeCoverageValidity(CoverageValidityBoundary):
    """適用日ごとに有効性の回答を差し替えられる再検証境界。"""

    def __init__(self, *, valid: bool = True) -> None:
        self.valid = valid
        self.calls: list[tuple[CorporateId, PatientId, date]] = []

    async def is_snapshot_valid(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
        snapshot: CoverageSnapshot,
        applied_on: date,
    ) -> bool:
        """呼び出し内容を記録し、設定された有効性を返す。"""
        del snapshot
        self.calls.append((corporate_id, patient_id, applied_on))
        return self.valid
