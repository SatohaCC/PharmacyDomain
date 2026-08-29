"""処方箋をApplication DTOへ変換して取得する処理。

用量は ``Decimal`` なので **文字列で返す**。``float`` へ落とすと 0.05刻みの
用量が丸められ、不均等服用の合計一致という不変条件が呼び出し元で再現できない。
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control import CorporateAccessBoundary, Permission
from app.application.prescription.support import load_prescription_or_raise
from app.base.domain.dosage import (
    DosageInstruction,
)
from app.base.domain.medicine import PublicExpenseBurden
from app.domain.corporate.primitives import CorporateId
from app.domain.prescription import (
    DepartmentInfo,
    DosageSupplement,
    GenericSubstitutionRestriction,
    MedicalInstitutionInfo,
    MedicineSupplement,
    PrescriberInfo,
    PrescriberResponse,
    Prescription,
    PrescriptionId,
    PrescriptionInquiry,
    PrescriptionManagementInfo,
    PrescriptionMedicine,
    PrescriptionPeriod,
    PrescriptionRepository,
    PrescriptionRp,
    UnitConversion,
)


@dataclass(frozen=True, kw_only=True)
class MedicalInstitutionDto:
    """保険医療機関の出力DTO。"""

    code_type: str
    code: str
    prefecture_code: str
    name: str
    postal_code: str | None
    address: str | None
    phone_number: str | None
    fax_number: str | None

    @classmethod
    def from_value(cls, value: MedicalInstitutionInfo) -> MedicalInstitutionDto:
        """医療機関情報からDTOを生成する。"""
        return cls(
            code_type=value.code_type.value,
            code=value.code.value,
            prefecture_code=value.prefecture_code.value,
            name=value.name.value,
            postal_code=(
                value.postal_code.value if value.postal_code is not None else None
            ),
            address=value.address.value if value.address is not None else None,
            phone_number=(
                value.phone_number.value if value.phone_number is not None else None
            ),
            fax_number=(
                value.fax_number.value if value.fax_number is not None else None
            ),
        )


@dataclass(frozen=True, kw_only=True)
class DepartmentDto:
    """診療科の出力DTO。"""

    code_type: str
    name: str
    code: str | None

    @classmethod
    def from_value(cls, value: DepartmentInfo) -> DepartmentDto:
        """診療科情報からDTOを生成する。"""
        return cls(
            code_type=value.code_type.value,
            name=value.name.value,
            code=value.code.value if value.code is not None else None,
        )


@dataclass(frozen=True, kw_only=True)
class PrescriberDto:
    """処方医の出力DTO。"""

    full_name: str
    full_name_kana: str
    code: str | None

    @classmethod
    def from_value(cls, value: PrescriberInfo) -> PrescriberDto:
        """処方医情報からDTOを生成する。"""
        return cls(
            full_name=value.names.full_name,
            full_name_kana=value.names.full_name_kana,
            code=value.code.value if value.code is not None else None,
        )


@dataclass(frozen=True, kw_only=True)
class PrescriptionPeriodDto:
    """交付日と使用期限の出力DTO。"""

    issued_date: str
    valid_to: str

    @classmethod
    def from_value(cls, value: PrescriptionPeriod) -> PrescriptionPeriodDto:
        """処方期間からDTOを生成する。"""
        return cls(
            issued_date=value.issued_date.value.isoformat(),
            valid_to=value.valid_to.value.isoformat(),
        )


@dataclass(frozen=True, kw_only=True)
class DosageInstructionDto:
    """用法の出力DTO。"""

    code_type: str
    name: str
    code: str | None
    daily_frequency: int | None

    @classmethod
    def from_value(cls, value: DosageInstruction) -> DosageInstructionDto:
        """用法からDTOを生成する。"""
        return cls(
            code_type=value.code_type.value,
            name=value.name.value,
            code=value.code.value if value.code is not None else None,
            daily_frequency=(
                value.daily_frequency.value
                if value.daily_frequency is not None
                else None
            ),
        )


@dataclass(frozen=True, kw_only=True)
class DosageSupplementDto:
    """用法補足の出力DTO。"""

    supplement_type: str
    text: str
    code: str | None
    site_code: str | None

    @classmethod
    def from_value(cls, value: DosageSupplement) -> DosageSupplementDto:
        """用法補足からDTOを生成する。"""
        return cls(
            supplement_type=value.supplement_type.value,
            text=value.text.value,
            code=value.code.value if value.code is not None else None,
            site_code=value.site_code.value if value.site_code is not None else None,
        )


@dataclass(frozen=True, kw_only=True)
class MedicineSupplementDto:
    """薬品補足（調製指示）の出力DTO。"""

    supplement_type: str
    text: str
    code: str | None

    @classmethod
    def from_value(cls, value: MedicineSupplement) -> MedicineSupplementDto:
        """薬品補足からDTOを生成する。"""
        return cls(
            supplement_type=value.supplement_type.value,
            text=value.text.value,
            code=value.code.value if value.code is not None else None,
        )


@dataclass(frozen=True, kw_only=True)
class SubstitutionRestrictionDto:
    """変更制限の出力DTO。"""

    restriction_type: str
    reason: str | None
    forbids_generic_substitution: bool

    @classmethod
    def from_value(
        cls, value: GenericSubstitutionRestriction
    ) -> SubstitutionRestrictionDto:
        """変更制限からDTOを生成する。"""
        return cls(
            restriction_type=value.restriction_type.value,
            reason=value.reason.value if value.reason is not None else None,
            forbids_generic_substitution=value.forbids_generic_substitution,
        )


@dataclass(frozen=True, kw_only=True)
class UnitConversionDto:
    """単位変換の出力DTO。"""

    factor: str
    tariff_unit: str

    @classmethod
    def from_value(cls, value: UnitConversion) -> UnitConversionDto:
        """単位変換からDTOを生成する。"""
        return cls(factor=str(value.factor.value), tariff_unit=value.tariff_unit.value)


@dataclass(frozen=True, kw_only=True)
class PublicExpenseBurdenDto:
    """公費負担区分の出力DTO。"""

    first: bool
    second: bool
    third: bool
    special: bool

    @classmethod
    def from_value(cls, value: PublicExpenseBurden) -> PublicExpenseBurdenDto:
        """公費負担区分からDTOを生成する。"""
        return cls(
            first=value.first,
            second=value.second,
            third=value.third,
            special=value.special,
        )


@dataclass(frozen=True, kw_only=True)
class PrescriptionMedicineDto:
    """処方薬品1明細の出力DTO。"""

    line_number: int
    code_type: str
    code: str | None
    name: str
    amount: str
    unit: str
    single_dose: str | None
    unequal_doses: tuple[str, ...]
    unit_conversion: UnitConversionDto | None
    substitution_restriction: SubstitutionRestrictionDto | None
    public_expense_burden: PublicExpenseBurdenDto | None
    supplements: tuple[MedicineSupplementDto, ...]

    @classmethod
    def from_value(cls, value: PrescriptionMedicine) -> PrescriptionMedicineDto:
        """処方薬品からDTOを生成する。"""
        return cls(
            line_number=value.line_number.value,
            code_type=value.identifier.code_type.value,
            code=(
                value.identifier.code.value
                if value.identifier.code is not None
                else None
            ),
            name=value.name.value,
            amount=str(value.amount.value),
            unit=value.unit.value,
            single_dose=(
                str(value.single_dose.value) if value.single_dose is not None else None
            ),
            unequal_doses=(
                tuple(str(dose.value) for dose in value.unequal_dosage.doses)
                if value.unequal_dosage is not None
                else ()
            ),
            unit_conversion=(
                UnitConversionDto.from_value(value.unit_conversion)
                if value.unit_conversion is not None
                else None
            ),
            substitution_restriction=(
                SubstitutionRestrictionDto.from_value(value.substitution_restriction)
                if value.substitution_restriction is not None
                else None
            ),
            public_expense_burden=(
                PublicExpenseBurdenDto.from_value(value.public_expense_burden)
                if value.public_expense_burden is not None
                else None
            ),
            supplements=tuple(
                MedicineSupplementDto.from_value(item) for item in value.supplements
            ),
        )


@dataclass(frozen=True, kw_only=True)
class PrescriptionRpDto:
    """剤（Rp）の出力DTO。"""

    rp_number: int
    category: str
    quantity: int
    dosage_instruction: DosageInstructionDto
    medicines: tuple[PrescriptionMedicineDto, ...]
    custom_category_name: str | None
    dosage_supplements: tuple[DosageSupplementDto, ...]

    @classmethod
    def from_value(cls, value: PrescriptionRp) -> PrescriptionRpDto:
        """剤（Rp）からDTOを生成する。"""
        return cls(
            rp_number=value.rp_number.value,
            category=value.category.value,
            quantity=value.quantity.value,
            dosage_instruction=DosageInstructionDto.from_value(
                value.dosage_instruction
            ),
            medicines=tuple(
                PrescriptionMedicineDto.from_value(item) for item in value.medicines
            ),
            custom_category_name=(
                value.custom_category_name.value
                if value.custom_category_name is not None
                else None
            ),
            dosage_supplements=tuple(
                DosageSupplementDto.from_value(item)
                for item in value.dosage_supplements
            ),
        )


@dataclass(frozen=True, kw_only=True)
class PrescriptionManagementInfoDto:
    """管理情報・特殊指示の出力DTO。"""

    refill_count: int | None
    split_total_count: int | None
    split_iteration: int | None
    residual_drug_instruction: str | None
    narcotic_license_number: str | None
    patient_address: str | None
    patient_phone_number: str | None
    notes: tuple[str, ...]
    clinical_info: tuple[str, ...]
    lab_data: tuple[str, ...]

    @classmethod
    def from_value(
        cls, value: PrescriptionManagementInfo
    ) -> PrescriptionManagementInfoDto:
        """管理情報からDTOを生成する。"""
        narcotic = value.narcotic
        return cls(
            refill_count=(
                value.refill.total_refill_count.value
                if value.refill is not None
                else None
            ),
            split_total_count=(
                value.split.total_split_count.value if value.split is not None else None
            ),
            split_iteration=(
                value.split.split_iteration.value if value.split is not None else None
            ),
            residual_drug_instruction=(
                value.residual_drug.instruction.value
                if value.residual_drug is not None
                else None
            ),
            narcotic_license_number=(
                narcotic.narcotic_license_number.value if narcotic is not None else None
            ),
            patient_address=(
                narcotic.patient_address.value if narcotic is not None else None
            ),
            patient_phone_number=(
                narcotic.patient_phone_number.value if narcotic is not None else None
            ),
            notes=tuple(item.value for item in value.notes.items),
            clinical_info=tuple(item.text.value for item in value.clinical_info),
            lab_data=tuple(item.text.value for item in value.lab_data),
        )


@dataclass(frozen=True, kw_only=True)
class PrescriberResponseDto:
    """疑義照会の回答の出力DTO。"""

    responded_by: str
    responded_at: str
    result_type: str
    content: str
    blocks_dispensing: bool

    @classmethod
    def from_value(cls, value: PrescriberResponse) -> PrescriberResponseDto:
        """回答からDTOを生成する。"""
        return cls(
            responded_by=value.responded_by.value,
            responded_at=value.responded_at.value.isoformat(),
            result_type=value.result_type.value,
            content=value.content.value,
            blocks_dispensing=value.blocks_dispensing,
        )


@dataclass(frozen=True, kw_only=True)
class PrescriptionInquiryDto:
    """疑義照会1件の出力DTO。"""

    inquiry_number: int
    pharmacist_id: str
    inquired_at: str
    category: str
    content: str
    response: PrescriberResponseDto | None
    is_open: bool

    @classmethod
    def from_entity(cls, inquiry: PrescriptionInquiry) -> PrescriptionInquiryDto:
        """疑義照会からDTOを生成する。"""
        return cls(
            inquiry_number=inquiry.inquiry_number.value,
            pharmacist_id=str(inquiry.pharmacist_id.value),
            inquired_at=inquiry.inquired_at.value.isoformat(),
            category=inquiry.category.value,
            content=inquiry.content.value,
            response=(
                PrescriberResponseDto.from_value(inquiry.response)
                if inquiry.response is not None
                else None
            ),
            is_open=inquiry.is_open,
        )


@dataclass(frozen=True, kw_only=True)
class PrescriptionDto:
    """処方箋の出力DTO。"""

    id: str
    corporate_id: str
    store_id: str
    patient_id: str
    source_type: str
    document_number: str
    status: str
    medical_institution: MedicalInstitutionDto
    department: DepartmentDto
    prescriber: PrescriberDto
    period: PrescriptionPeriodDto
    rps: tuple[PrescriptionRpDto, ...]
    management_info: PrescriptionManagementInfoDto
    inquiries: tuple[PrescriptionInquiryDto, ...]
    coverage_selection_record_id: str | None
    has_open_inquiry: bool

    @classmethod
    def from_entity(cls, prescription: Prescription) -> PrescriptionDto:
        """処方箋集約からDTOを生成する。"""
        record_id = prescription.coverage_selection_record_id
        return cls(
            id=str(prescription.id.value),
            corporate_id=str(prescription.corporate_id.value),
            store_id=str(prescription.store_id.value),
            patient_id=str(prescription.patient_id.value),
            source_type=prescription.source_type.value,
            document_number=prescription.document_number.value,
            status=prescription.status.value,
            medical_institution=MedicalInstitutionDto.from_value(
                prescription.medical_institution
            ),
            department=DepartmentDto.from_value(prescription.department),
            prescriber=PrescriberDto.from_value(prescription.prescriber),
            period=PrescriptionPeriodDto.from_value(prescription.period),
            rps=tuple(PrescriptionRpDto.from_value(rp) for rp in prescription.rps),
            management_info=PrescriptionManagementInfoDto.from_value(
                prescription.management_info
            ),
            inquiries=tuple(
                PrescriptionInquiryDto.from_entity(inquiry)
                for inquiry in prescription.inquiries
            ),
            coverage_selection_record_id=(
                str(record_id.value) if record_id is not None else None
            ),
            has_open_inquiry=prescription.has_open_inquiry,
        )


@dataclass(frozen=True, kw_only=True)
class GetPrescriptionQuery:
    """処方箋取得の入力データ。"""

    corporate_id: str
    prescription_id: str


class GetPrescriptionUseCase:
    """法人境界を確認して処方箋を取得する。"""

    def __init__(
        self,
        repository: PrescriptionRepository,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access

    async def execute(self, query: GetPrescriptionQuery) -> PrescriptionDto:
        """指定法人の処方箋をDTOで返す。エンティティは返さない。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.VIEW_PRESCRIPTION,
        )
        prescription = await load_prescription_or_raise(
            self._repository,
            corporate_id=corporate_id,
            prescription_id=PrescriptionId.parse(query.prescription_id),
        )
        return PrescriptionDto.from_entity(prescription)
