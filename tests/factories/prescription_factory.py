"""処方箋テストで共有する組み立てヘルパー。

``Prescription`` は剤（Rp）→薬品明細と2段の入れ子を持ち、各テストで丸ごと
組み立てると Arrange が読みづらくなるため、既定値を持つファクトリをここへ集約する。
ドメイン層テストとアプリケーション層テストの双方から使う。
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from app.base.domain.dosage import (
    DosageCodeType,
    DosageInstruction,
    DosageName,
)
from app.base.domain.medicine import (
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
)
from app.base.domain.value_object import PersonNames
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientId
from app.domain.prescription import (
    DepartmentCodeType,
    DepartmentInfo,
    DepartmentName,
    GenericSubstitutionRestriction,
    GenericSubstitutionRestrictionType,
    InquiryCategory,
    InquiryContent,
    InquiryResponseContent,
    InquiryResultType,
    InquiryTimestamp,
    MedicalInstitutionCode,
    MedicalInstitutionCodeType,
    MedicalInstitutionInfo,
    MedicalInstitutionName,
    MedicalInstitutionPrefectureCode,
    PrescriberInfo,
    PrescriberName,
    PrescriberResponse,
    Prescription,
    PrescriptionDocumentNumber,
    PrescriptionIssuedDate,
    PrescriptionManagementInfo,
    PrescriptionMedicine,
    PrescriptionPeriod,
    PrescriptionRp,
    PrescriptionSourceType,
    PrescriptionValidTo,
)
from app.domain.staff.primitives import StaffId
from app.domain.store.primitives import StoreId

ISSUED_ON = date(2026, 8, 24)
VALID_TO = date(2026, 8, 27)


def create_medical_institution(
    *,
    code: str = "1234567",
    prefecture_code: str = "13",
    name: str = "医療法人 サンプル病院",
) -> MedicalInstitutionInfo:
    """医療機関情報を組み立てる。"""
    return MedicalInstitutionInfo(
        code_type=MedicalInstitutionCodeType.MEDICAL,
        code=MedicalInstitutionCode(code),
        prefecture_code=MedicalInstitutionPrefectureCode(prefecture_code),
        name=MedicalInstitutionName(name),
    )


def create_department(name: str = "内科") -> DepartmentInfo:
    """診療科情報を組み立てる（コードなし）。"""
    return DepartmentInfo(
        code_type=DepartmentCodeType.NONE,
        name=DepartmentName(name),
    )


def create_prescriber(
    last_name: str = "佐藤",
    first_name: str = "一郎",
    last_name_kana: str = "サトウ",
    first_name_kana: str = "イチロウ",
) -> PrescriberInfo:
    """処方医情報を組み立てる。"""
    return PrescriberInfo(
        names=PersonNames.create(
            last_name=last_name,
            first_name=first_name,
            last_name_kana=last_name_kana,
            first_name_kana=first_name_kana,
        )
    )


def create_period(
    issued_on: date = ISSUED_ON, valid_to: date = VALID_TO
) -> PrescriptionPeriod:
    """処方期間を組み立てる。"""
    return PrescriptionPeriod(
        issued_date=PrescriptionIssuedDate(issued_on),
        valid_to=PrescriptionValidTo(valid_to),
    )


def create_dosage_instruction(name: str = "1日3回毎食後") -> DosageInstruction:
    """用法を組み立てる（コードなし）。"""
    return DosageInstruction(
        code_type=DosageCodeType.NONE,
        name=DosageName(name),
    )


def create_medicine(
    *,
    line_number: int = 1,
    code_type: MedicineCodeType = MedicineCodeType.YJ,
    code: str | None = "2171022F1029",
    name: str = "ノルバスク錠２．５ｍｇ",
    amount: str = "3",
    unit: str = "錠",
    burden: PublicExpenseBurden | None = None,
    restriction: GenericSubstitutionRestrictionType | None = None,
) -> PrescriptionMedicine:
    """処方薬品の1明細を組み立てる。"""
    return PrescriptionMedicine(
        line_number=MedicineLineNumber(line_number),
        identifier=MedicineIdentifier(
            code_type=code_type,
            code=MedicineCode(code) if code is not None else None,
        ),
        name=MedicineName(name),
        amount=DosageAmount(Decimal(amount)),
        unit=MedicineUnit(unit),
        public_expense_burden=burden,
        substitution_restriction=(
            GenericSubstitutionRestriction(restriction_type=restriction)
            if restriction is not None
            else None
        ),
    )


def create_rp(
    *,
    rp_number: int = 1,
    category: DosageFormCategory = DosageFormCategory.INTERNAL,
    quantity: int = 14,
    medicines: tuple[PrescriptionMedicine, ...] | None = None,
) -> PrescriptionRp:
    """剤（Rp）を組み立てる。"""
    return PrescriptionRp(
        rp_number=RpNumber(rp_number),
        category=category,
        quantity=DispensingQuantity(quantity),
        dosage_instruction=create_dosage_instruction(),
        medicines=medicines if medicines is not None else (create_medicine(),),
    )


def create_prescription(
    *,
    corporate_id: CorporateId | None = None,
    store_id: StoreId | None = None,
    patient_id: PatientId | None = None,
    source_type: PrescriptionSourceType = PrescriptionSourceType.PAPER_QR,
    document_number: str = "1234567890123456",
    rps: tuple[PrescriptionRp, ...] | None = None,
    management_info: PrescriptionManagementInfo | None = None,
) -> Prescription:
    """処方箋集約を組み立てる。"""
    return Prescription.create(
        corporate_id=corporate_id
        if corporate_id is not None
        else CorporateId.generate(),
        store_id=store_id if store_id is not None else StoreId.generate(),
        patient_id=patient_id if patient_id is not None else PatientId.generate(),
        source_type=source_type,
        document_number=PrescriptionDocumentNumber(document_number),
        medical_institution=create_medical_institution(),
        department=create_department(),
        prescriber=create_prescriber(),
        period=create_period(),
        rps=rps if rps is not None else (create_rp(),),
        management_info=management_info,
    )


def create_inquiry_timestamp(
    moment: datetime | None = None,
) -> InquiryTimestamp:
    """疑義照会の日時を組み立てる（UTC）。"""
    return InquiryTimestamp(
        moment if moment is not None else datetime(2026, 8, 24, 1, 30, tzinfo=UTC)
    )


def start_inquiry(
    prescription: Prescription,
    *,
    pharmacist_id: StaffId | None = None,
    category: InquiryCategory = InquiryCategory.DOSAGE,
    content: str = "1日3錠は用量超過ではないか確認したい。",
) -> Prescription:
    """処方箋に疑義照会を1件追加する。"""
    return prescription.start_inquiry(
        pharmacist_id=pharmacist_id
        if pharmacist_id is not None
        else StaffId.generate(),
        category=category,
        content=InquiryContent(content),
        inquired_at=create_inquiry_timestamp(),
    )


def create_response(
    *,
    result_type: InquiryResultType = InquiryResultType.UNCHANGED,
    content: str = "処方どおりで問題ない旨の回答を得た。",
    responded_by: str = "佐藤 一郎",
) -> PrescriberResponse:
    """疑義照会の回答を組み立てる。"""
    return PrescriberResponse(
        responded_by=PrescriberName(responded_by),
        responded_at=create_inquiry_timestamp(datetime(2026, 8, 24, 2, 0, tzinfo=UTC)),
        result_type=result_type,
        content=InquiryResponseContent(content),
    )
