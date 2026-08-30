"""Dispensingコンテキストの複合 Value Object。

集約とその子要素（``DispensedRp`` / ``DispensedMedicine``）は
``dispensing_process.py`` にある。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar

from app.domain.dispensing.exceptions import QuantityAdjustmentInvalidError
from app.domain.dispensing.primitives import (
    AuditNotes,
    AuditTimestamp,
    QuantityAdjustmentReason,
    SubstitutionCategory,
    SubstitutionReason,
    VerificationNotes,
    VerificationResult,
    VerificationTimestamp,
)
from app.domain.foundation.value_object import ValueObject
from app.domain.shared.medicine import (
    DispensingQuantity,
    MedicineIdentifier,
    MedicineName,
)
from app.domain.staff.primitives import StaffId


@dataclass(frozen=True, kw_only=True)
class SubstitutionDetail(ValueObject):
    """軸1: 代替調剤の記録。処方薬品を別の薬品へ置き換えたときだけ持つ。

    処方箋の変更制限（別表16 の 3〜6・8）に反しないかは処方箋集約を参照する
    ため、ここでは判定できない。
    """

    category: SubstitutionCategory
    original_identifier: MedicineIdentifier
    original_name: MedicineName
    reason: SubstitutionReason | None = None

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "category": "代替調剤種別",
        "original_identifier": "変更前の薬品コード",
        "original_name": "変更前の薬品名称",
        "reason": "変更理由",
    }

    def describes_change_from(
        self, identifier: MedicineIdentifier, name: MedicineName
    ) -> bool:
        """調剤後の薬品と比べて、実際に変更が起きているかを返す。

        変更前後が完全に同じなら代替調剤として記録する意味がない。判定に
        調剤後の値が要るので、拒否するのは :class:`DispensedMedicine` 側。
        """
        return not (
            self.original_identifier == identifier and self.original_name == name
        )

    @property
    def is_generic_substitution(self) -> bool:
        """後発医薬品への変更調剤か。"""
        return self.category is SubstitutionCategory.GENERIC_SUBSTITUTION


@dataclass(frozen=True, kw_only=True)
class QuantityAdjustment(ValueObject):
    """軸2: 減数調剤の記録。処方時の数量を併せて保持する。

    処方時の数量を持たないと、減数したことを後から検証できない。
    """

    prescribed_quantity: DispensingQuantity
    reason: QuantityAdjustmentReason

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "prescribed_quantity": "処方時の調剤数量",
        "reason": "数量調整の理由",
    }

    def ensure_reduces(self, dispensed_quantity: DispensingQuantity) -> None:
        """実際の調剤数量が処方時より少ないことを検証する。

        ``DispensingQuantity`` が正の整数であることは型が保証するので、
        ここでは「0より大きい」を重複して検証しない。

        Raises:
            QuantityAdjustmentInvalidError: 処方時の数量以上である場合。
        """
        if dispensed_quantity.value >= self.prescribed_quantity.value:
            raise QuantityAdjustmentInvalidError(
                prescribed=self.prescribed_quantity.value,
                dispensed=dispensed_quantity.value,
            )


@dataclass(frozen=True, kw_only=True)
class DispensingPrescriptionAudit(ValueObject):
    """処方鑑査の記録。調剤調製の**前**に、処方内容そのものを確認した結果。

    相互作用・重複投薬・用量の確認であり、調製された薬剤を確認する
    :class:`DispensingVerification` とは対象もタイミングも異なる。
    """

    auditor_id: StaffId
    audited_at: AuditTimestamp
    has_issues: bool
    notes: AuditNotes | None = None

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "auditor_id": "処方鑑査者",
        "audited_at": "処方鑑査日時",
        "has_issues": "疑義の有無",
        "notes": "処方鑑査所見",
    }


@dataclass(frozen=True, kw_only=True)
class DispensingVerification(ValueObject):
    """最終鑑査（調剤鑑査）の記録。調製された薬剤が処方どおりかの確認。"""

    verifier_id: StaffId
    verified_at: VerificationTimestamp
    result: VerificationResult
    notes: VerificationNotes | None = None

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "verifier_id": "最終鑑査者",
        "verified_at": "最終鑑査日時",
        "result": "鑑査結果",
        "notes": "最終鑑査所見",
    }

    @property
    def is_passed(self) -> bool:
        """鑑査に合格したか。"""
        return self.result.is_passed
