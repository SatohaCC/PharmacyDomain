"""Prescriptionの参照境界を各Repositoryへ接続する実アダプタ。"""

from __future__ import annotations

from dataclasses import fields

from app.application.composition.reference_support import load_store_in_corporate
from app.application.prescription.exceptions import (
    PrescriptionCoverageSelectionNotFoundError,
    PrescriptionPatientNotFoundError,
    PrescriptionPharmacistNotFoundError,
    PrescriptionStoreNotFoundError,
)
from app.application.prescription.reference import (
    PatientReferenceBoundary,
    PublicExpenseAvailabilityBoundary,
    StaffQualificationBoundary,
    StoreReferenceBoundary,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientId
from app.domain.patient.repository import PatientRepository
from app.domain.reception.primitives import CoverageSelectionRecordId
from app.domain.reception.repository import CoverageSelectionRecordRepository
from app.domain.shared.public_expense import PublicExpenseBurden
from app.domain.staff.primitives import StaffId, StaffQualifications
from app.domain.staff.repository import StaffRepository
from app.domain.store.primitives import StoreId
from app.domain.store.repository import StoreRepository

#: 資格台帳の公費順位（第一〜第四）から、処方箋の公費枠への対応。
#:
#: 両者は別軸である。処方箋の枠は第一/第二/第三/**特殊**で、特殊公費の負担者番号は
#: 数字以外を含みうるため ``ClaimPublicPayerNumber``（8桁）を満たせず、資格台帳から
#: 写せない。したがって ``special`` はどの順位にも対応づけず、常に「裏付けなし」に
#: なる。第四公費も処方箋側に受け皿が無いので、どの枠も立てない。
#:
#: 対応表に無い枠を ``True`` にすると、裏付けの無い公費負担が処方箋へ固定される。
_PRIORITY_TO_SLOT: dict[int, str] = {1: "first", 2: "second", 3: "third"}

#: 資格台帳から裏付けられない処方箋の公費枠。
_UNBACKED_SLOTS = frozenset({"special"})


def _verify_slot_mapping_is_complete() -> None:
    """公費枠の対応表が実フィールドを網羅していることを検証する。

    処方箋の枠を1つ足したとき、対応表にも ``_UNBACKED_SLOTS`` にも入れ忘れると、
    その枠だけ裏付けの判定が静かに ``False`` 固定になる。読み込み時に落とす。
    最適化実行（``python -O``）でも省略されないよう ``assert`` は使わない。
    """
    declared = frozenset(item.name for item in fields(PublicExpenseBurden))
    mapped = frozenset(_PRIORITY_TO_SLOT.values())
    if mapped | _UNBACKED_SLOTS != declared:
        raise RuntimeError(
            "処方箋の公費枠が、資格台帳の順位との対応表と一致していません。"
        )
    if mapped & _UNBACKED_SLOTS:
        raise RuntimeError("裏付け不能とした公費枠に順位が対応づけられています。")


_verify_slot_mapping_is_complete()


class PrescriptionStoreReferenceAdapter(StoreReferenceBoundary):
    """店舗の存在と法人境界だけを確認し、店舗集約は渡さない。"""

    def __init__(self, repository: StoreRepository) -> None:
        self._repository = repository

    async def require_exists(
        self,
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
    ) -> None:
        """未存在・別法人の店舗を、存在を隠す404相当へ畳む。"""
        store = await load_store_in_corporate(
            self._repository,
            corporate_id=corporate_id,
            store_id=store_id,
        )
        if store is None:
            raise PrescriptionStoreNotFoundError()


class PrescriptionPatientReferenceAdapter(PatientReferenceBoundary):
    """患者の存在と法人境界だけを確認し、患者集約は渡さない。"""

    def __init__(self, repository: PatientRepository) -> None:
        self._repository = repository

    async def require_exists(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
    ) -> None:
        """未存在・別法人の患者を、存在を隠す404相当へ畳む。"""
        patient = await self._repository.get(
            corporate_id=corporate_id,
            patient_id=patient_id,
        )
        if patient is None:
            raise PrescriptionPatientNotFoundError()


class PrescriptionStaffQualificationAdapter(StaffQualificationBoundary):
    """スタッフの保有資格だけを取り出し、Staff集約は渡さない。"""

    def __init__(self, repository: StaffRepository) -> None:
        self._repository = repository

    async def get_qualifications(
        self,
        *,
        corporate_id: CorporateId,
        staff_id: StaffId,
    ) -> StaffQualifications:
        """未存在・別法人のスタッフを404相当へ畳み、資格をそのまま返す。

        薬剤師かどうかの判定はここで行わない。判定を境界側へ寄せると、同じ規則が
        実装ごとに分岐する。資格が空でも在籍しているので例外にしない。
        """
        staff = await self._repository.get(
            corporate_id=corporate_id,
            staff_id=staff_id,
        )
        if staff is None:
            raise PrescriptionPharmacistNotFoundError()
        return staff.qualifications


class CoverageSelectionPublicExpenseAdapter(PublicExpenseAvailabilityBoundary):
    """受付で確定した資格選択から、処方箋の公費枠の裏付けを導く。

    資格台帳の順位（第一〜第四）と処方箋の枠（第一/第二/第三/特殊）は別軸で、
    その対応づけはどちらのコンテキストにも属さない。Composition に閉じ込める。
    """

    def __init__(self, repository: CoverageSelectionRecordRepository) -> None:
        self._repository = repository

    async def available_burden(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
        coverage_selection_record_id: CoverageSelectionRecordId,
    ) -> PublicExpenseBurden:
        """履歴に存在する公費順位を、処方箋の枠へ写して返す。

        患者が違う履歴も、存在を漏らさないよう未存在と同じ例外へ畳む。
        """
        record = await self._repository.get(
            corporate_id=corporate_id,
            record_id=coverage_selection_record_id,
        )
        if record is None or record.patient_id != patient_id:
            raise PrescriptionCoverageSelectionNotFoundError()
        slots = {
            _PRIORITY_TO_SLOT[item.values.priority.value]: True
            for item in record.selection.public_expenses
            if item.values.priority.value in _PRIORITY_TO_SLOT
        }
        return PublicExpenseBurden(**slots)
