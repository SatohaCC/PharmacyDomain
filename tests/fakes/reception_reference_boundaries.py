"""Reception Applicationが依存する参照境界のフェイク実装。

AGENTS.md「Boundaryの例外契約」が求める「定義だけで raise されない例外を残さない」
を実行可能にするため、各Protocolの ``Raises:`` に書かれた例外をここで実際に送出する。
"""

from __future__ import annotations

from app.application.reception.exceptions import (
    ReceptionCoverageSelectionError,
    ReceptionPatientNotFoundError,
    ReceptionStoreNotFoundError,
)
from app.application.reception.reference import (
    CoverageSelectionBoundary,
    CoverageValidityBoundary,
    PatientReferenceBoundary,
    StoreReferenceBoundary,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientId
from app.domain.reception.coverage_selection import CoverageSelection
from app.domain.reception.primitives import CoverageAppliedOn
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
            raise ReceptionStoreNotFoundError()


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
            raise ReceptionPatientNotFoundError()


class FakeCoverageSelectionSource(CoverageSelectionBoundary):
    """資格IDの組に対して用意された選択を返す境界。"""

    def __init__(self) -> None:
        self.selections: dict[tuple[str, ...], CoverageSelection] = {}

    def register(
        self,
        *,
        coverage_ids: tuple[str, ...],
        selection: CoverageSelection,
    ) -> None:
        """資格IDの組に対応する選択を登録する。"""
        self.selections[coverage_ids] = selection

    async def build_selection(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
        coverage_ids: tuple[str, ...],
        applied_on: CoverageAppliedOn,
    ) -> CoverageSelection:
        """登録のない資格IDの組は選択エラーとして扱う。"""
        del corporate_id, patient_id, applied_on
        selection = self.selections.get(coverage_ids)
        if selection is None:
            raise ReceptionCoverageSelectionError()
        return selection


class FakeCoverageValidity(CoverageValidityBoundary):
    """適用日ごとに有効性の回答を差し替えられる再検証境界。"""

    def __init__(self, *, valid: bool = True) -> None:
        self.valid = valid
        self.calls: list[tuple[CorporateId, PatientId, CoverageSelection]] = []

    async def is_selection_valid(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
        selection: CoverageSelection,
        applied_on: CoverageAppliedOn,
    ) -> bool:
        """呼び出し内容を記録し、設定された有効性を返す。"""
        del applied_on
        self.calls.append((corporate_id, patient_id, selection))
        return self.valid
