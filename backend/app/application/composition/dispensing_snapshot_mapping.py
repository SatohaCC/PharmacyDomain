"""処方原本の業務情報を調剤が所有する不変値へ変換する。"""

from app.domain.dispensing.primitives import (
    DailyFrequency,
    DosageCode,
    DosageCodeType,
    DosageName,
    GenericSubstitutionRestrictionType,
    InquiryNumber,
    InquiryResultType,
    MedicineCode,
    MedicineCodeType,
    MedicineLineNumber,
    MedicineName,
    PrescriptionStatus,
    RpNumber,
    SourceRefillCount,
    SourceSplitCount,
)
from app.domain.dispensing.value_objects import (
    DosageInstruction,
    InquiryResponse,
    MedicineIdentifier,
    PrescriptionInquiry,
    PrescriptionMedicine,
    PrescriptionRp,
    PrescriptionSource,
    SubstitutionRestriction,
)
from app.domain.prescription.entities import Prescription
from app.domain.prescription.value_objects import (
    DosageInstruction as SourceDosageInstruction,
)


def dispensing_dosage(value: SourceDosageInstruction) -> DosageInstruction:
    """処方記載の用法を調剤時点の用法へ固定する。"""
    return DosageInstruction(
        code_type=DosageCodeType(value.code_type.value),
        name=DosageName(value.name.value),
        code=DosageCode(value.code.value) if value.code is not None else None,
        daily_frequency=DailyFrequency(value.daily_frequency.value)
        if value.daily_frequency is not None
        else None,
    )


def prescription_source(value: Prescription) -> PrescriptionSource:
    """各判定材料を明示的に写し、原本の実装型を利用側へ渡さない。"""
    return PrescriptionSource(
        prescription_id=value.id,
        corporate_id=value.corporate_id,
        patient_id=value.patient_id,
        status=PrescriptionStatus(value.status.value),
        issued_on=value.period.issued_date.value,
        valid_to=value.period.valid_to.value,
        split_count=(
            SourceSplitCount(value.management_info.split.total_split_count.value)
            if value.management_info.split is not None
            else None
        ),
        refill_count=(
            SourceRefillCount(value.management_info.refill.total_refill_count.value)
            if value.management_info.refill is not None
            else None
        ),
        rps=tuple(
            PrescriptionRp(
                rp_number=RpNumber(rp.rp_number.value),
                medicines=tuple(
                    PrescriptionMedicine(
                        line_number=MedicineLineNumber(medicine.line_number.value),
                        identifier=MedicineIdentifier(
                            code_type=MedicineCodeType(
                                medicine.identifier.code_type.value
                            ),
                            code=MedicineCode(medicine.identifier.code.value)
                            if medicine.identifier.code is not None
                            else None,
                        ),
                        name=MedicineName(medicine.name.value),
                        substitution_restriction=SubstitutionRestriction(
                            restriction_type=GenericSubstitutionRestrictionType(
                                medicine.substitution_restriction.restriction_type.value
                            )
                        )
                        if medicine.substitution_restriction is not None
                        else None,
                    )
                    for medicine in rp.medicines
                ),
            )
            for rp in value.rps
        ),
        inquiries=tuple(
            PrescriptionInquiry(
                inquiry_number=InquiryNumber(inquiry.id.value),
                response=InquiryResponse(
                    result_type=InquiryResultType(inquiry.response.result_type.value)
                )
                if inquiry.response is not None
                else None,
            )
            for inquiry in value.inquiries
        ),
    )
