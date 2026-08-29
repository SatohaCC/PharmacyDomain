"""処方箋登録の入力DTO。

``Prescription`` は剤（Rp）→薬品明細と2段の入れ子を持つため、Commandを平坦な
フィールド列にすると「何番目の要素が何番目の薬品に対応するか」が並び順の規約に
なる。AGENTS.md「選択は枠で持つ」と同じ理由で、入力側も入れ子のまま受け取る。

**用量は ``str`` で受け取る。** ``float`` を経由すると ``Decimal(0.1)`` のように
誤差が入り、不均等服用の合計一致判定が正当な処方を弾く。境界で ``float`` を
止めるため、``Decimal`` への変換はこの層の ``support.py`` だけが行う。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, kw_only=True)
class MedicalInstitutionInput:
    """保険医療機関の入力（JAHIS レコードNo.1 / No.2）。"""

    code_type: str
    code: str
    prefecture_code: str
    name: str
    postal_code: str | None = None
    address: str | None = None
    phone_number: str | None = None
    fax_number: str | None = None


@dataclass(frozen=True, kw_only=True)
class DepartmentInput:
    """診療科の入力（JAHIS レコードNo.4）。"""

    code_type: str
    name: str
    code: str | None = None


@dataclass(frozen=True, kw_only=True)
class PrescriberInput:
    """処方医の入力（JAHIS レコードNo.5）。"""

    last_name: str
    first_name: str
    last_name_kana: str
    first_name_kana: str
    code: str | None = None


@dataclass(frozen=True, kw_only=True)
class DosageInstructionInput:
    """用法の入力（JAHIS レコードNo.111）。"""

    code_type: str
    name: str
    code: str | None = None
    daily_frequency: int | None = None


@dataclass(frozen=True, kw_only=True)
class DosageSupplementInput:
    """用法補足の入力（JAHIS レコードNo.181 / 処方編 別表14）。"""

    supplement_type: str
    text: str
    code: str | None = None
    site_code: str | None = None


@dataclass(frozen=True, kw_only=True)
class MedicineSupplementInput:
    """薬品補足のうち調製指示の入力（処方編 別表16 の 1・2・7）。"""

    supplement_type: str
    text: str
    code: str | None = None


@dataclass(frozen=True, kw_only=True)
class SubstitutionRestrictionInput:
    """薬品補足のうち変更制限の入力（処方編 別表16 の 3〜6・8）。"""

    restriction_type: str
    reason: str | None = None


@dataclass(frozen=True, kw_only=True)
class UnitConversionInput:
    """単位変換の入力（JAHIS レコードNo.211）。"""

    factor: str
    tariff_unit: str


@dataclass(frozen=True, kw_only=True)
class PublicExpenseBurdenInput:
    """公費負担区分の入力（JAHIS レコードNo.231）。"""

    first: bool = False
    second: bool = False
    third: bool = False
    special: bool = False


@dataclass(frozen=True, kw_only=True)
class MedicineInput:
    """処方薬品1明細の入力（JAHIS レコードNo.201 と紐づくレコード群）。"""

    line_number: int
    code_type: str
    name: str
    amount: str
    unit: str
    code: str | None = None
    unit_conversion: UnitConversionInput | None = None
    unequal_doses: tuple[str, ...] = ()
    single_dose: str | None = None
    substitution_restriction: SubstitutionRestrictionInput | None = None
    public_expense_burden: PublicExpenseBurdenInput | None = None
    supplements: tuple[MedicineSupplementInput, ...] = ()


@dataclass(frozen=True, kw_only=True)
class RpInput:
    """剤（Rp）の入力（JAHIS レコードNo.101 / No.111 / No.181）。"""

    rp_number: int
    category: str
    quantity: int
    dosage_instruction: DosageInstructionInput
    medicines: tuple[MedicineInput, ...]
    custom_category_name: str | None = None
    dosage_supplements: tuple[DosageSupplementInput, ...] = ()


@dataclass(frozen=True, kw_only=True)
class PrescriptionManagementInput:
    """処方箋の管理情報・特殊指示の入力。

    麻薬処方箋情報とリフィル指示はここで受け取れるが、いずれも医薬品マスタの
    裏付けが要る（``NarcoticPrescriptionService`` / ``RefillEligibilityService``）。
    マスタが無い間、これらを含む処方箋の登録は fail-closed で失敗する。
    """

    refill_count: int | None = None
    split_total_count: int | None = None
    split_iteration: int | None = None
    residual_drug_instruction: str | None = None
    narcotic_license_number: str | None = None
    patient_address: str | None = None
    patient_phone_number: str | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)
    clinical_info: tuple[str, ...] = field(default_factory=tuple)
    lab_data: tuple[str, ...] = field(default_factory=tuple)
