"""Prescriptionユースケース間で共有する入力変換処理。

``to_optional_text`` は Shared Kernel の定義を**再エクスポートするだけ**にする。
複製するとコンテキストごとに正規化ルールが分岐する（AGENTS.md「空文字の正規化」）。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum

from app.application.prescription.exceptions import PrescriptionNotFoundError
from app.application.prescription.inputs import (
    DepartmentInput,
    DosageInstructionInput,
    DosageSupplementInput,
    MedicalInstitutionInput,
    MedicineInput,
    MedicineSupplementInput,
    PrescriberInput,
    PrescriptionManagementInput,
    PublicExpenseBurdenInput,
    RpInput,
    SubstitutionRestrictionInput,
    UnitConversionInput,
)
from app.base.application.support import to_optional_text
from app.base.domain.dosage import (
    DailyFrequency,
    DosageCode,
    DosageCodeType,
    DosageInstruction,
    DosageName,
)
from app.base.domain.exceptions import DomainValidationError
from app.base.domain.medicine import (
    ConversionFactor,
    DispensingQuantity,
    DosageAmount,
    DosageFormCategory,
    MedicineCode,
    MedicineCodeType,
    MedicineIdentifier,
    MedicineLineNumber,
    MedicineName,
    MedicineUnit,
    PublicExpenseBurden,
    RpNumber,
    SingleDoseAmount,
)
from app.base.domain.value_object import PersonNames
from app.domain.corporate.primitives import CorporateId
from app.domain.prescription import (
    ApplicationSiteCode,
    ClinicalInformation,
    ClinicalInformationText,
    DepartmentCode,
    DepartmentCodeType,
    DepartmentInfo,
    DepartmentName,
    DosageFormName,
    DosageSupplement,
    DosageSupplementCode,
    DosageSupplementText,
    DosageSupplementType,
    GenericSubstitutionRestriction,
    GenericSubstitutionRestrictionType,
    LaboratoryData,
    LaboratoryDataText,
    MedicalInstitutionAddressLine,
    MedicalInstitutionCode,
    MedicalInstitutionCodeType,
    MedicalInstitutionFaxNumber,
    MedicalInstitutionInfo,
    MedicalInstitutionName,
    MedicalInstitutionPhoneNumber,
    MedicalInstitutionPostalCode,
    MedicalInstitutionPrefectureCode,
    MedicineSupplement,
    MedicineSupplementText,
    MedicineSupplementType,
    NarcoticLicenseNumber,
    NarcoticPrescriptionDetails,
    PatientAddressLine,
    PatientPhoneNumber,
    PrescriberCode,
    PrescriberInfo,
    Prescription,
    PrescriptionId,
    PrescriptionIssuedDate,
    PrescriptionManagementInfo,
    PrescriptionMedicine,
    PrescriptionNote,
    PrescriptionNotes,
    PrescriptionPeriod,
    PrescriptionRepository,
    PrescriptionRp,
    PrescriptionSourceType,
    PrescriptionValidTo,
    RefillCount,
    RefillInstruction,
    ResidualDrugConfirmation,
    ResidualDrugInstruction,
    SplitCount,
    SplitInstruction,
    SplitIteration,
    SubstitutionRestrictionReason,
    UnequalDosageInstruction,
    UnitConversion,
)

__all__ = [
    "build_department",
    "build_management_info",
    "build_medical_institution",
    "build_period",
    "build_prescriber",
    "build_rps",
    "load_prescription_or_raise",
    "parse_enum",
    "parse_source_type",
    "required_text",
    "to_optional_text",
]


def required_text(raw: str | None, field_name: str) -> str:
    """必須文字列を正規化し、未入力ならドメイン例外を送出する。"""
    value = to_optional_text(raw)
    if value is None:
        raise DomainValidationError(f"{field_name}は必須です。")
    return value


def parse_enum[E: StrEnum](enum_type: type[E], raw: str, field_name: str) -> E:
    """入力文字列を指定の列挙へ変換する。

    列挙ごとに同じ ``try/except`` を書き写すと、区分が増えるたびに変換漏れの
    余地が増えるため1箇所に閉じる。
    """
    try:
        return enum_type(raw)
    except ValueError as exc:
        raise DomainValidationError(f"{field_name}が不正です。") from exc


def parse_source_type(raw: str) -> PrescriptionSourceType:
    """入力文字列を処方箋の受領元形式へ変換する。"""
    return parse_enum(PrescriptionSourceType, raw, "処方箋受領元形式")


def _parse_decimal(raw: str, field_name: str) -> Decimal:
    """入力文字列を ``Decimal`` へ変換する。

    ``float`` を経由しないので、0.05刻みの用量でも誤差が入らない。
    """
    try:
        return Decimal(raw.strip())
    except (ArithmeticError, ValueError) as exc:
        raise DomainValidationError(f"{field_name}は数値で指定してください。") from exc


def build_medical_institution(
    source: MedicalInstitutionInput,
) -> MedicalInstitutionInfo:
    """医療機関情報を構成する。"""
    postal_code = to_optional_text(source.postal_code)
    address = to_optional_text(source.address)
    phone_number = to_optional_text(source.phone_number)
    fax_number = to_optional_text(source.fax_number)
    return MedicalInstitutionInfo(
        code_type=parse_enum(
            MedicalInstitutionCodeType, source.code_type, "医療機関コード種別"
        ),
        code=MedicalInstitutionCode(required_text(source.code, "医療機関コード")),
        prefecture_code=MedicalInstitutionPrefectureCode(
            required_text(source.prefecture_code, "医療機関都道府県コード")
        ),
        name=MedicalInstitutionName(required_text(source.name, "医療機関名称")),
        postal_code=(
            MedicalInstitutionPostalCode(postal_code)
            if postal_code is not None
            else None
        ),
        address=(
            MedicalInstitutionAddressLine(address) if address is not None else None
        ),
        phone_number=(
            MedicalInstitutionPhoneNumber(phone_number)
            if phone_number is not None
            else None
        ),
        fax_number=(
            MedicalInstitutionFaxNumber(fax_number) if fax_number is not None else None
        ),
    )


def build_department(source: DepartmentInput) -> DepartmentInfo:
    """診療科情報を構成する。"""
    code = to_optional_text(source.code)
    return DepartmentInfo(
        code_type=parse_enum(DepartmentCodeType, source.code_type, "診療科コード種別"),
        name=DepartmentName(required_text(source.name, "診療科名")),
        code=DepartmentCode(code) if code is not None else None,
    )


def build_prescriber(source: PrescriberInput) -> PrescriberInfo:
    """処方医情報を構成する。"""
    code = to_optional_text(source.code)
    return PrescriberInfo(
        names=PersonNames.create(
            last_name=required_text(source.last_name, "処方医の姓"),
            first_name=required_text(source.first_name, "処方医の名"),
            last_name_kana=required_text(source.last_name_kana, "処方医の姓カナ"),
            first_name_kana=required_text(source.first_name_kana, "処方医の名カナ"),
        ),
        code=PrescriberCode(code) if code is not None else None,
    )


def build_period(*, issued_date: date, valid_to: date | None) -> PrescriptionPeriod:
    """処方期間を構成する。

    使用期限の指定が無い場合は交付日を含めて4日間の既定値を用いる。
    ここで ``date.today()`` を使わないのは AGENTS.md「資格の時間境界」と同じ理由で、
    ruff の ``DTZ011`` が禁止している。
    """
    issued = PrescriptionIssuedDate(issued_date)
    if valid_to is None:
        return PrescriptionPeriod.with_default_validity(issued)
    return PrescriptionPeriod(
        issued_date=issued, valid_to=PrescriptionValidTo(valid_to)
    )


def _build_dosage_instruction(source: DosageInstructionInput) -> DosageInstruction:
    """用法を構成する。"""
    code = to_optional_text(source.code)
    return DosageInstruction(
        code_type=parse_enum(DosageCodeType, source.code_type, "用法コード種別"),
        name=DosageName(required_text(source.name, "用法名称")),
        code=DosageCode(code) if code is not None else None,
        daily_frequency=(
            DailyFrequency(source.daily_frequency)
            if source.daily_frequency is not None
            else None
        ),
    )


def _build_dosage_supplement(source: DosageSupplementInput) -> DosageSupplement:
    """用法補足を構成する。"""
    code = to_optional_text(source.code)
    site_code = to_optional_text(source.site_code)
    return DosageSupplement(
        supplement_type=parse_enum(
            DosageSupplementType, source.supplement_type, "用法補足区分"
        ),
        text=DosageSupplementText(required_text(source.text, "用法補足情報")),
        code=DosageSupplementCode(code) if code is not None else None,
        site_code=ApplicationSiteCode(site_code) if site_code is not None else None,
    )


def _build_medicine_supplement(source: MedicineSupplementInput) -> MedicineSupplement:
    """薬品補足（調製指示）を構成する。"""
    code = to_optional_text(source.code)
    return MedicineSupplement(
        supplement_type=parse_enum(
            MedicineSupplementType, source.supplement_type, "薬品補足区分"
        ),
        text=MedicineSupplementText(required_text(source.text, "薬品補足情報")),
        code=DosageSupplementCode(code) if code is not None else None,
    )


def _build_substitution_restriction(
    source: SubstitutionRestrictionInput,
) -> GenericSubstitutionRestriction:
    """変更制限を構成する。"""
    reason = to_optional_text(source.reason)
    return GenericSubstitutionRestriction(
        restriction_type=parse_enum(
            GenericSubstitutionRestrictionType, source.restriction_type, "変更制限区分"
        ),
        reason=SubstitutionRestrictionReason(reason) if reason is not None else None,
    )


def _build_unit_conversion(source: UnitConversionInput) -> UnitConversion:
    """単位変換を構成する。"""
    return UnitConversion(
        factor=ConversionFactor(_parse_decimal(source.factor, "単位変換係数")),
        tariff_unit=MedicineUnit(required_text(source.tariff_unit, "薬価収載単位")),
    )


def _build_public_expense_burden(
    source: PublicExpenseBurdenInput,
) -> PublicExpenseBurden:
    """公費負担区分を構成する。"""
    return PublicExpenseBurden(
        first=source.first,
        second=source.second,
        third=source.third,
        special=source.special,
    )


def _build_medicine_identifier(source: MedicineInput) -> MedicineIdentifier:
    """薬品識別子（コード種別とコード）を構成する。"""
    code = to_optional_text(source.code)
    return MedicineIdentifier(
        code_type=parse_enum(MedicineCodeType, source.code_type, "薬品コード種別"),
        code=MedicineCode(code) if code is not None else None,
    )


def _build_unequal_dosage(
    source: MedicineInput,
) -> UnequalDosageInstruction | None:
    """不均等服用指示を構成する。"""
    if not source.unequal_doses:
        return None
    return UnequalDosageInstruction(
        doses=tuple(
            DosageAmount(_parse_decimal(dose, "各回服用量"))
            for dose in source.unequal_doses
        )
    )


def _build_medicine(source: MedicineInput) -> PrescriptionMedicine:
    """処方薬品の1明細を構成する。"""
    single_dose = to_optional_text(source.single_dose)
    return PrescriptionMedicine(
        line_number=MedicineLineNumber(source.line_number),
        identifier=_build_medicine_identifier(source),
        name=MedicineName(required_text(source.name, "薬品名称")),
        amount=DosageAmount(_parse_decimal(source.amount, "分量")),
        unit=MedicineUnit(required_text(source.unit, "単位名")),
        unit_conversion=(
            _build_unit_conversion(source.unit_conversion)
            if source.unit_conversion is not None
            else None
        ),
        unequal_dosage=_build_unequal_dosage(source),
        single_dose=(
            SingleDoseAmount(_parse_decimal(single_dose, "1回服用量"))
            if single_dose is not None
            else None
        ),
        substitution_restriction=(
            _build_substitution_restriction(source.substitution_restriction)
            if source.substitution_restriction is not None
            else None
        ),
        public_expense_burden=(
            _build_public_expense_burden(source.public_expense_burden)
            if source.public_expense_burden is not None
            else None
        ),
        supplements=tuple(
            _build_medicine_supplement(item) for item in source.supplements
        ),
    )


def _build_rp(source: RpInput) -> PrescriptionRp:
    """剤（Rp）を構成する。"""
    custom_category_name = to_optional_text(source.custom_category_name)
    return PrescriptionRp(
        rp_number=RpNumber(source.rp_number),
        category=parse_enum(DosageFormCategory, source.category, "剤形区分"),
        quantity=DispensingQuantity(source.quantity),
        dosage_instruction=_build_dosage_instruction(source.dosage_instruction),
        medicines=tuple(_build_medicine(item) for item in source.medicines),
        custom_category_name=(
            DosageFormName(custom_category_name)
            if custom_category_name is not None
            else None
        ),
        dosage_supplements=tuple(
            _build_dosage_supplement(item) for item in source.dosage_supplements
        ),
    )


def build_rps(sources: tuple[RpInput, ...]) -> tuple[PrescriptionRp, ...]:
    """剤（Rp）の一覧を構成する。"""
    return tuple(_build_rp(source) for source in sources)


def _build_refill(source: PrescriptionManagementInput) -> RefillInstruction | None:
    """リフィル指示を構成する。"""
    if source.refill_count is None:
        return None
    return RefillInstruction(total_refill_count=RefillCount(source.refill_count))


def _build_split(source: PrescriptionManagementInput) -> SplitInstruction | None:
    """医師の分割指示を構成する。片方だけの指定は受け付けない。"""
    total = source.split_total_count
    iteration = source.split_iteration
    if total is None and iteration is None:
        return None
    if total is None or iteration is None:
        raise DomainValidationError(
            "分割指示は全分割回数と当該分割回の両方を指定してください。"
        )
    return SplitInstruction(
        total_split_count=SplitCount(total),
        split_iteration=SplitIteration(iteration),
    )


def _build_narcotic(
    source: PrescriptionManagementInput,
) -> NarcoticPrescriptionDetails | None:
    """麻薬処方箋情報を構成する。3項目は揃っていなければならない。"""
    license_number = to_optional_text(source.narcotic_license_number)
    address = to_optional_text(source.patient_address)
    phone_number = to_optional_text(source.patient_phone_number)
    if license_number is None and address is None and phone_number is None:
        return None
    if license_number is None or address is None or phone_number is None:
        raise DomainValidationError(
            "麻薬処方箋情報は麻薬施用者免許番号・患者住所・患者電話番号を"
            "すべて指定してください。"
        )
    return NarcoticPrescriptionDetails(
        narcotic_license_number=NarcoticLicenseNumber(license_number),
        patient_address=PatientAddressLine(address),
        patient_phone_number=PatientPhoneNumber(phone_number),
    )


def _build_residual_drug(
    source: PrescriptionManagementInput,
) -> ResidualDrugConfirmation | None:
    """残薬確認指示を構成する。"""
    residual = to_optional_text(source.residual_drug_instruction)
    if residual is None:
        return None
    return ResidualDrugConfirmation(
        instruction=parse_enum(ResidualDrugInstruction, residual, "残薬確認対応")
    )


def build_management_info(
    source: PrescriptionManagementInput | None,
) -> PrescriptionManagementInfo:
    """処方箋の管理情報・特殊指示を構成する。"""
    if source is None:
        return PrescriptionManagementInfo()
    return PrescriptionManagementInfo(
        refill=_build_refill(source),
        split=_build_split(source),
        narcotic=_build_narcotic(source),
        residual_drug=_build_residual_drug(source),
        notes=PrescriptionNotes(
            items=tuple(
                PrescriptionNote(required_text(item, "備考")) for item in source.notes
            )
        ),
        clinical_info=tuple(
            ClinicalInformation(
                text=ClinicalInformationText(required_text(item, "臨床情報"))
            )
            for item in source.clinical_info
        ),
        lab_data=tuple(
            LaboratoryData(text=LaboratoryDataText(required_text(item, "検査値情報")))
            for item in source.lab_data
        ),
    )


async def load_prescription_or_raise(
    repository: PrescriptionRepository,
    *,
    corporate_id: CorporateId,
    prescription_id: PrescriptionId,
) -> Prescription:
    """指定法人の処方箋を取得し、存在しなければ404相当を送出する。"""
    prescription = await repository.get(
        corporate_id=corporate_id,
        prescription_id=prescription_id,
    )
    if prescription is None:
        raise PrescriptionNotFoundError()
    return prescription
