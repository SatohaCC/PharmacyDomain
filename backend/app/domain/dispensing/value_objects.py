"""dispensingの複合値と参照スナップショット。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import ClassVar

from app.domain.corporate.identifiers import CorporateId
from app.domain.dispensing.exceptions import (
    DispensedMedicineRequiredError,
    DuplicatedDispensedLineNumberError,
    DuplicatedPreparationMethodError,
    InquiryReferenceRequiredError,
    QuantityAdjustmentInvalidError,
    SubstitutionWithoutChangeError,
)
from app.domain.dispensing.primitives import (
    AuditNotes,
    AuditTimestamp,
    DailyFrequency,
    DispensingQuantity,
    DosageAmount,
    DosageCode,
    DosageCodeType,
    DosageFormCategory,
    DosageName,
    GenericSubstitutionRestrictionType,
    InquiryNumber,
    InquiryResultType,
    MedicineCode,
    MedicineCodeType,
    MedicineLineNumber,
    MedicineName,
    MedicineUnit,
    PreparationMethod,
    PrescriptionStatus,
    QuantityAdjustmentReason,
    RpNumber,
    SourceRefillCount,
    SourceSplitCount,
    SubstitutionCategory,
    SubstitutionReason,
    VerificationNotes,
    VerificationResult,
    VerificationTimestamp,
)
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.foundation.value_object import ValueObject
from app.domain.patient.identifiers import PatientId
from app.domain.prescription.identifiers import PrescriptionId
from app.domain.shared.public_expense import PublicExpenseBurden
from app.domain.staff.identifiers import StaffId


@dataclass(frozen=True, kw_only=True)
class DispensedMedicine(ValueObject):
    """調剤した医薬品の1明細。

    変更調剤の実績は以下の3つの観点に分かれます：
    1. 薬品自体の変更（代替調剤）: ``substitution``（本明細で保持）
    2. 調製方法の変更（一包化・粉砕等）: ``preparations``（本明細で保持）
    3. 数量の調整（減数調剤）: 剤単位で管理されるため :class:`DispensedRp` で保持
    """

    line_number: MedicineLineNumber
    identifier: MedicineIdentifier
    name: MedicineName
    amount: DosageAmount
    unit: MedicineUnit
    substitution: SubstitutionDetail | None = None
    preparations: tuple[PreparationMethod, ...] = ()
    public_expense_burden: PublicExpenseBurden | None = None

    def validate(self) -> None:
        """この明細だけで判定できる不変条件を検証する。"""
        self._ensure_substitution_describes_a_change()
        self._ensure_preparations_are_unique()

    def _ensure_substitution_describes_a_change(self) -> None:
        """代替調剤の変更前と変更後が同一でないことを検証する。"""
        if self.substitution is None:
            return
        if not self.substitution.describes_change_from(self.identifier, self.name):
            raise SubstitutionWithoutChangeError(medicine_name=self.name.value)

    def _ensure_preparations_are_unique(self) -> None:
        """同一の調製方法が重複して指定されていないことを検証する。

        一包化と粉砕のように「異なる」調製方法の組み合わせは正当ですが、
        同じ調製方法の重複指定は拒否します。
        """
        if len(self.preparations) != len(set(self.preparations)):
            raise DuplicatedPreparationMethodError()

    @property
    def is_substituted(self) -> bool:
        """処方原本から薬品そのものを置き換えたか。"""
        return self.substitution is not None


@dataclass(frozen=True, kw_only=True)
class DispensedRp(ValueObject):
    """調剤した剤（Rp）。処方箋の剤に ``rp_number`` で対応する。"""

    rp_number: RpNumber
    category: DosageFormCategory
    quantity: DispensingQuantity
    dosage_instruction: DosageInstruction
    medicines: tuple[DispensedMedicine, ...]
    quantity_adjustment: QuantityAdjustment | None = None

    def validate(self) -> None:
        """剤の構造的な不変条件を検証する。"""
        self._ensure_has_medicine()
        self._ensure_line_numbers_are_unique()
        self._ensure_quantity_adjustment_reduces()

    def _ensure_has_medicine(self) -> None:
        """薬品明細が1件以上あることを検証する。"""
        if not self.medicines:
            raise DispensedMedicineRequiredError()

    def _ensure_line_numbers_are_unique(self) -> None:
        """剤（RP）内の薬品明細連番が重複していないことを検証する。

        減数調剤や分割調剤において処方箋の一部の薬品のみを調剤する場合があるため、
        連番の欠番は許容されますが、重複は拒否します。
        """
        numbers = [medicine.line_number for medicine in self.medicines]
        if len(numbers) != len(set(numbers)):
            raise DuplicatedDispensedLineNumberError()

    def _ensure_quantity_adjustment_reduces(self) -> None:
        """減数調剤なら、実際の数量が処方時より少ないことを検証する。"""
        if self.quantity_adjustment is None:
            return
        self.quantity_adjustment.ensure_reduces(self.quantity)

    @property
    def is_quantity_adjusted(self) -> bool:
        """減数調剤を行ったか。"""
        return self.quantity_adjustment is not None

    @property
    def has_substitution(self) -> bool:
        """この剤に代替調剤を行った薬品が含まれるか。"""
        return any(medicine.is_substituted for medicine in self.medicines)


@dataclass(frozen=True, kw_only=True)
class SubstitutionRestriction(ValueObject):
    """処方原本に記載された変更制限。"""

    restriction_type: GenericSubstitutionRestrictionType


@dataclass(frozen=True, kw_only=True)
class PrescriptionMedicine(ValueObject):
    """薬品の対応と変更制限の判定に必要な原本情報。"""

    line_number: MedicineLineNumber
    identifier: MedicineIdentifier
    name: MedicineName
    substitution_restriction: SubstitutionRestriction | None


@dataclass(frozen=True, kw_only=True)
class PrescriptionRp(ValueObject):
    """原本の剤番号と薬品の対応。"""

    rp_number: RpNumber
    medicines: tuple[PrescriptionMedicine, ...]


@dataclass(frozen=True, kw_only=True)
class InquiryResponse(ValueObject):
    """原本で確定した疑義照会の回答区分。"""

    result_type: InquiryResultType


@dataclass(frozen=True, kw_only=True)
class PrescriptionInquiry(ValueObject):
    """照会連番と合意結果の対応。"""

    inquiry_number: InquiryNumber
    response: InquiryResponse | None


@dataclass(frozen=True, kw_only=True)
class PrescriptionSource(ValueObject):
    """原本の同一性と、調剤の判定に必要な固定値だけを保持する。"""

    prescription_id: PrescriptionId
    corporate_id: CorporateId
    patient_id: PatientId
    status: PrescriptionStatus
    rps: tuple[PrescriptionRp, ...]
    inquiries: tuple[PrescriptionInquiry, ...]
    issued_on: date
    valid_to: date
    split_count: SourceSplitCount | None
    refill_count: SourceRefillCount | None

    def validate(self) -> None:
        """期間と使用回数が判定可能な値であることを保証する。"""
        if self.valid_to < self.issued_on:
            raise DomainValidationError("原本の使用期限が交付日より前です。")
        if any(
            count is not None and count < 1
            for count in (
                (self.split_count.value if self.split_count is not None else None),
                (self.refill_count.value if self.refill_count is not None else None),
            )
        ):
            raise DomainValidationError("原本の使用回数は1以上で指定してください。")


@dataclass(frozen=True, kw_only=True)
class MedicineIdentifier(ValueObject):
    """薬品コード種別とコードを不可分に束ねる値オブジェクト。

    桁数がコード種別に依存するため ``MedicineCode`` 単独では自己検証できない。
    種別ごとに型を分けると、処方箋明細のフィールド型が動的になるため採らない。
    コードなしの処方やマスタ未収載の持参薬も表せるため、医薬品マスタ行の存在を
    意味しない。ここで所有するのは、外部データ間で薬品を照合するコード語彙である。
    """

    code_type: MedicineCodeType
    code: MedicineCode | None = None

    _FIELD_LABELS: ClassVar[dict[str, str]] = {
        "code_type": "薬品コード種別",
        "code": "薬品コード",
    }

    def validate(self) -> None:
        """コード種別とコードの有無の整合性を検証する。"""
        if self.code_type is MedicineCodeType.NONE:
            if self.code is not None:
                raise DomainValidationError(
                    "薬品コード種別が「コードなし」のときは薬品コードを指定できません。"
                )
            return
        if self.code is None:
            raise DomainValidationError(
                f"薬品コード種別が「{self.code_type.label}」のときは"
                "薬品コードが必要です。"
            )


@dataclass(frozen=True, kw_only=True)
class DosageInstruction(ValueObject):
    """用法（JAHIS レコードNo.111 / 処方編 用法レコード）。

    調剤側でも同じ値を持つ。減数調剤は「用法及び用量の変更は行わずに投与日数等を
    減らす調剤」なので、調剤結果の用法は処方箋の用法と一致する。
    """

    code_type: DosageCodeType
    name: DosageName
    code: DosageCode | None = None
    daily_frequency: DailyFrequency | None = None

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "code_type": "用法コード種別",
        "name": "用法名称",
        "code": "用法コード",
        "daily_frequency": "1日回数",
    }

    def validate(self) -> None:
        """コード種別とコードの有無の整合性を検証する。

        ``MedicineIdentifier`` と同じ形の検証であり、コンテキスト固有の業務例外
        ではなく ``DomainValidationError`` を送出する（Shared Kernel は各
        コンテキストの例外型を知らない）。
        """
        if self.code_type is DosageCodeType.NONE:
            if self.code is not None:
                raise DomainValidationError(
                    "用法コード種別が「コードなし」のときは用法コードを指定できません。"
                )
            return
        if self.code is None:
            raise DomainValidationError(
                f"用法コード種別が「{self.code_type.label}」のときは"
                "用法コードが必要です。"
            )


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
    inquiry_number: InquiryNumber | None = None

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "category": "代替調剤種別",
        "original_identifier": "変更前の薬品コード",
        "original_name": "変更前の薬品名称",
        "reason": "変更理由",
        "inquiry_number": "疑義照会連番",
    }

    def validate(self) -> None:
        """疑義照会に基づく処方変更調剤の場合、照会連番が必須であることを検証する。"""
        if (
            self.category is SubstitutionCategory.INQUIRY_MODIFIED
            and self.inquiry_number is None
        ):
            raise InquiryReferenceRequiredError()

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
    inquiry_number: InquiryNumber | None = None

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "prescribed_quantity": "処方時の調剤数量",
        "reason": "数量調整の理由",
        "inquiry_number": "疑義照会連番",
    }

    def validate(self) -> None:
        """疑義照会合意による数量調整の場合、照会連番が必須であることを検証する。"""
        if (
            self.reason is QuantityAdjustmentReason.INQUIRY_AGREED
            and self.inquiry_number is None
        ):
            raise InquiryReferenceRequiredError()

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


@dataclass(frozen=True, kw_only=True)
class PharmacistQualification(ValueObject):
    """スタッフ境界で確認された薬剤師資格の保有事実。"""

    has_pharmacist: bool
