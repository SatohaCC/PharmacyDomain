"""Prescription Applicationが依存する参照境界のフェイク実装。

AGENTS.md「Boundaryの例外契約」が求める「定義だけで raise されない例外を残さない」
を実行可能にするため、各Protocolの ``Raises:`` に書かれた例外をここで実際に送出する。

**既定値で「該当しない」を返さない。** 医薬品の規制区分も公費枠も、登録していない
ものは「不明」または「存在しない」として扱う。フェイクが安全側の答えを勝手に
埋めると、fail-closed の設計がテスト上だけ無効になる。
"""

from __future__ import annotations

from datetime import date

from app.application.prescription.exceptions import (
    PrescriptionCoverageSelectionNotFoundError,
    PrescriptionPatientNotFoundError,
    PrescriptionPharmacistNotFoundError,
    PrescriptionStoreNotFoundError,
)
from app.application.prescription.reference import (
    MedicineRestrictionBoundary,
    PatientReferenceBoundary,
    PublicExpenseAvailabilityBoundary,
    StaffQualificationBoundary,
    StoreReferenceBoundary,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientId
from app.domain.prescription import (
    MedicineClassification,
)
from app.domain.reception.primitives import CoverageSelectionRecordId
from app.domain.shared.medicine import (
    MedicineIdentifier,
)
from app.domain.shared.public_expense import PublicExpenseBurden
from app.domain.staff.primitives import StaffId, StaffQualifications
from app.domain.store.primitives import StoreId


class FakePrescriptionStoreReference(StoreReferenceBoundary):
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
            raise PrescriptionStoreNotFoundError()


class FakePrescriptionPatientReference(PatientReferenceBoundary):
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
            raise PrescriptionPatientNotFoundError()


class FakeStaffQualificationSource(StaffQualificationBoundary):
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

        資格を持たないだけのスタッフは在籍しているので例外にしない
        （空の ``StaffQualifications`` を登録すればその状態を表せる）。
        """
        qualifications = self.qualifications.get((corporate_id, staff_id))
        if qualifications is None:
            raise PrescriptionPharmacistNotFoundError()
        return qualifications


class FakeMedicineRestrictionSource(MedicineRestrictionBoundary):
    """薬品ごとに登録された規制区分だけを返す境界。"""

    def __init__(self) -> None:
        self.classifications: dict[MedicineIdentifier, MedicineClassification] = {}

    def register(self, classification: MedicineClassification) -> None:
        """医薬品マスタに1件登録する。"""
        self.classifications[classification.identifier] = classification

    async def classify(
        self,
        *,
        identifiers: tuple[MedicineIdentifier, ...],
        as_of: date,
    ) -> dict[MedicineIdentifier, MedicineClassification]:
        """登録済みの薬品だけを返す。未登録は戻り値に含めない。

        「該当しない」既定値で埋めないのが要点。埋めるとマスタ未登録の薬品で
        麻薬・リフィルの判定が素通りし、fail-closed が壊れる。

        このフェイクは時点を持たないので ``as_of`` は使わない。時点で答えが
        変わることは実アダプタ（Composition）のテストが確かめる。
        """
        del as_of
        return {
            identifier: self.classifications[identifier]
            for identifier in identifiers
            if identifier in self.classifications
        }


class FakePublicExpenseAvailability(PublicExpenseAvailabilityBoundary):
    """資格選択履歴ごとに登録された公費枠を返す境界。"""

    def __init__(self) -> None:
        self.burdens: dict[
            tuple[CorporateId, PatientId, CoverageSelectionRecordId],
            PublicExpenseBurden,
        ] = {}

    def register(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
        coverage_selection_record_id: CoverageSelectionRecordId,
        burden: PublicExpenseBurden,
    ) -> None:
        """資格選択履歴に存在する公費枠を設定する。"""
        key = (corporate_id, patient_id, coverage_selection_record_id)
        self.burdens[key] = burden

    async def available_burden(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
        coverage_selection_record_id: CoverageSelectionRecordId,
    ) -> PublicExpenseBurden:
        """未登録・別法人・別患者の履歴は404相当を送出する。"""
        key = (corporate_id, patient_id, coverage_selection_record_id)
        burden = self.burdens.get(key)
        if burden is None:
            raise PrescriptionCoverageSelectionNotFoundError()
        return burden
