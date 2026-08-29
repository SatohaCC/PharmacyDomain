"""Dispensing Applicationが依存する参照境界のフェイク実装。

AGENTS.md「Boundaryの例外契約」が求める「定義だけで raise されない例外を残さない」
を実行可能にするため、各Protocolの ``Raises:`` に書かれた例外をここで実際に送出する。

処方箋の参照・完了は、実運用では Composition Root の実アダプタが
``PrescriptionRepository`` を包んで実装する。ここでは同じ契約をインメモリで満たす。
"""

from __future__ import annotations

from app.application.dispensing.exceptions import (
    DispensingPrescriptionNotFoundError,
    DispensingStaffNotFoundError,
    DispensingStoreNotFoundError,
)
from app.application.dispensing.reference import (
    PrescriptionCompletionBoundary,
    PrescriptionReferenceBoundary,
    StaffQualificationBoundary,
    StoreReferenceBoundary,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.prescription.prescription import Prescription
from app.domain.prescription.primitives import PrescriptionId, PrescriptionStatus
from app.domain.staff.primitives import StaffId, StaffQualifications
from app.domain.store.primitives import StoreId


class FakeDispensingStoreReference(StoreReferenceBoundary):
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
            raise DispensingStoreNotFoundError()


class FakePrescriptionSource(
    PrescriptionReferenceBoundary, PrescriptionCompletionBoundary
):
    """処方箋集約を保持し、参照と調剤済への遷移の両方を提供する境界。

    実運用でも同じ ``PrescriptionRepository`` を包む1つのアダプタが両Protocolを
    満たすので、フェイクも1クラスにまとめる。
    """

    def __init__(self) -> None:
        self.prescriptions: dict[tuple[CorporateId, PrescriptionId], Prescription] = {}

    def register(self, prescription: Prescription) -> None:
        """処方箋を登録する。"""
        key = (prescription.corporate_id, prescription.id)
        self.prescriptions[key] = prescription

    async def get_or_raise(
        self,
        *,
        corporate_id: CorporateId,
        prescription_id: PrescriptionId,
    ) -> Prescription:
        """未登録・別法人の処方箋は404相当を送出する。"""
        prescription = self.prescriptions.get((corporate_id, prescription_id))
        if prescription is None:
            raise DispensingPrescriptionNotFoundError()
        return prescription

    async def complete_dispensing(
        self,
        *,
        corporate_id: CorporateId,
        prescription_id: PrescriptionId,
    ) -> None:
        """処方箋を調剤済へ遷移させる。すでに調剤済なら何もしない（冪等）。"""
        key = (corporate_id, prescription_id)
        prescription = self.prescriptions.get(key)
        if prescription is None:
            raise DispensingPrescriptionNotFoundError()
        if prescription.status is PrescriptionStatus.DISPENSED:
            return
        self.prescriptions[key] = prescription.complete_dispensing()


class FakeDispensingStaffQualificationSource(StaffQualificationBoundary):
    """法人ごとに登録されたスタッフの保有資格を返す境界。"""

    def __init__(self) -> None:
        self.qualifications: dict[tuple[CorporateId, StaffId], StaffQualifications] = {}

    def register(
        self,
        *,
        corporate_id: CorporateId,
        staff_id: StaffId,
        qualifications: StaffQualifications,
    ) -> None:
        """指定法人にスタッフを在籍させ、保有資格を設定する。"""
        self.qualifications[(corporate_id, staff_id)] = qualifications

    async def get_qualifications(
        self,
        *,
        corporate_id: CorporateId,
        staff_id: StaffId,
    ) -> StaffQualifications:
        """未登録・別法人のスタッフは404相当を送出する。

        資格を持たないだけのスタッフは在籍しているので例外にしない。
        """
        qualifications = self.qualifications.get((corporate_id, staff_id))
        if qualifications is None:
            raise DispensingStaffNotFoundError()
        return qualifications
