"""調剤の整合性判定に必要な処方原本の不変情報。"""

from dataclasses import dataclass
from datetime import date

from app.domain.corporate.identifiers import CorporateId
from app.domain.dispensing.reference_primitives import (
    GenericSubstitutionRestrictionType,
    InquiryNumber,
    InquiryResultType,
    MedicineLineNumber,
    MedicineName,
    PrescriptionStatus,
    RpNumber,
)
from app.domain.dispensing.reference_values import MedicineIdentifier
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.foundation.value_object import ValueObject
from app.domain.patient.identifiers import PatientId
from app.domain.prescription.identifiers import PrescriptionId


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
    split_count: int | None
    refill_count: int | None

    def validate(self) -> None:
        """期間と使用回数が判定可能な値であることを保証する。"""
        if self.valid_to < self.issued_on:
            raise DomainValidationError("原本の使用期限が交付日より前です。")
        if any(
            count is not None and count < 1
            for count in (self.split_count, self.refill_count)
        ):
            raise DomainValidationError("原本の使用回数は1以上で指定してください。")
