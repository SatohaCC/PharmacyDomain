"""Applicationのdispensing_snapshot_mappingを定義する。"""

from __future__ import annotations

from app.domain.dispensing.primitives import (
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
    InquiryResponse,
    MedicineIdentifier,
    PrescriptionInquiry,
    PrescriptionMedicine,
    PrescriptionRp,
    PrescriptionSource,
    SubstitutionRestriction,
)
from app.domain.prescription.entities import Prescription


def prescription_source(value: Prescription) -> PrescriptionSource:
    """各判定材料を明示的に写し、原本の実装型を利用側へ渡さない。"""
    return PrescriptionSource(
        prescription_id=value.id,
        corporate_id=value.corporate_id,
        patient_id=value.patient_id,
        status=PrescriptionStatus(value.status.value),
        issued_on=value.period.issued_date.value,
        valid_to=value.period.valid_to.value,
        split_count=SourceSplitCount(
            value.management_info.split.total_split_count.value
        )
        if value.management_info.split is not None
        else None,
        refill_count=SourceRefillCount(
            value.management_info.refill.total_refill_count.value
        )
        if value.management_info.refill is not None
        else None,
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
