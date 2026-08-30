"""調剤テストで共有する組み立てヘルパー。

``DispensingProcess`` は剤（Rp）→薬品明細と2段の入れ子を持つため、既定値を
持つファクトリをここへ集約する。ドメイン層テストとアプリケーション層テストの
双方から使う。
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing import (
    DispensedDate,
    DispensedMedicine,
    DispensedRp,
    DispensingIteration,
    DispensingProcess,
    DispensingSplitReason,
    DispensingTimestamp,
    PreparationMethod,
    QuantityAdjustment,
    QuantityAdjustmentReason,
    SubstitutionCategory,
    SubstitutionDetail,
    VerificationResult,
    VerificationTimestamp,
)
from app.domain.patient.primitives import PatientId
from app.domain.prescription.primitives import PrescriptionId
from app.domain.shared.dosage import DosageCodeType, DosageInstruction, DosageName
from app.domain.shared.medicine import (
    DispensingQuantity,
    DosageAmount,
    DosageFormCategory,
    MedicineCode,
    MedicineCodeType,
    MedicineIdentifier,
    MedicineLineNumber,
    MedicineName,
    MedicineUnit,
    RpNumber,
)
from app.domain.staff.primitives import StaffId
from app.domain.store.primitives import StoreId

DISPENSED_ON = date(2026, 8, 24)
STARTED_AT = datetime(2026, 8, 24, 1, 30, tzinfo=UTC)
MEDICINE_CODE = "2171022F1029"
MEDICINE_NAME = "ノルバスク錠２．５ｍｇ"
GENERIC_CODE = "2171022F1037"
GENERIC_NAME = "アムロジピンＯＤ錠２．５ｍｇ「サワイ」"


def create_identifier(code: str = MEDICINE_CODE) -> MedicineIdentifier:
    """YJコードの薬品識別子を組み立てる。"""
    return MedicineIdentifier(code_type=MedicineCodeType.YJ, code=MedicineCode(code))


def create_substitution(
    *,
    category: SubstitutionCategory = SubstitutionCategory.GENERIC_SUBSTITUTION,
    original_code: str = MEDICINE_CODE,
    original_name: str = MEDICINE_NAME,
) -> SubstitutionDetail:
    """代替調剤の記録を組み立てる。"""
    return SubstitutionDetail(
        category=category,
        original_identifier=create_identifier(original_code),
        original_name=MedicineName(original_name),
    )


def create_dispensed_medicine(
    *,
    line_number: int = 1,
    code: str = MEDICINE_CODE,
    name: str = MEDICINE_NAME,
    amount: str = "3",
    unit: str = "錠",
    substitution: SubstitutionDetail | None = None,
    preparations: tuple[PreparationMethod, ...] = (),
) -> DispensedMedicine:
    """調剤した薬品の1明細を組み立てる。"""
    return DispensedMedicine(
        line_number=MedicineLineNumber(line_number),
        identifier=create_identifier(code),
        name=MedicineName(name),
        amount=DosageAmount(Decimal(amount)),
        unit=MedicineUnit(unit),
        substitution=substitution,
        preparations=preparations,
    )


def create_dosage_instruction(name: str = "1日3回毎食後") -> DosageInstruction:
    """用法を組み立てる（コードなし）。"""
    return DosageInstruction(code_type=DosageCodeType.NONE, name=DosageName(name))


def create_dispensed_rp(
    *,
    rp_number: int = 1,
    category: DosageFormCategory = DosageFormCategory.INTERNAL,
    quantity: int = 14,
    medicines: tuple[DispensedMedicine, ...] | None = None,
    quantity_adjustment: QuantityAdjustment | None = None,
) -> DispensedRp:
    """調剤した剤（Rp）を組み立てる。"""
    return DispensedRp(
        rp_number=RpNumber(rp_number),
        category=category,
        quantity=DispensingQuantity(quantity),
        dosage_instruction=create_dosage_instruction(),
        medicines=medicines
        if medicines is not None
        else (create_dispensed_medicine(),),
        quantity_adjustment=quantity_adjustment,
    )


def create_quantity_adjustment(
    *,
    prescribed_quantity: int = 28,
    reason: QuantityAdjustmentReason = QuantityAdjustmentReason.RESIDUAL_DRUG,
) -> QuantityAdjustment:
    """減数調剤の記録を組み立てる。"""
    return QuantityAdjustment(
        prescribed_quantity=DispensingQuantity(prescribed_quantity),
        reason=reason,
    )


def create_dispensing(
    *,
    corporate_id: CorporateId | None = None,
    store_id: StoreId | None = None,
    patient_id: PatientId | None = None,
    prescription_id: PrescriptionId | None = None,
    iteration: int = 1,
    dispensed_on: date = DISPENSED_ON,
    dispenser_id: StaffId | None = None,
    dispensed_rps: tuple[DispensedRp, ...] | None = None,
    split_reason: DispensingSplitReason | None = None,
) -> DispensingProcess:
    """調剤セッションを開始した状態で組み立てる。"""
    return DispensingProcess.start(
        corporate_id=corporate_id
        if corporate_id is not None
        else CorporateId.generate(),
        store_id=store_id if store_id is not None else StoreId.generate(),
        patient_id=patient_id if patient_id is not None else PatientId.generate(),
        prescription_id=prescription_id
        if prescription_id is not None
        else PrescriptionId.generate(),
        iteration=DispensingIteration(iteration),
        dispensed_date=DispensedDate(dispensed_on),
        dispenser_id=dispenser_id if dispenser_id is not None else StaffId.generate(),
        started_at=DispensingTimestamp(STARTED_AT),
        dispensed_rps=dispensed_rps
        if dispensed_rps is not None
        else (create_dispensed_rp(),),
        split_reason=split_reason,
    )


def verify_passed(
    process: DispensingProcess,
    *,
    verifier_id: StaffId | None = None,
) -> DispensingProcess:
    """最終鑑査に合格させる。調剤者とは別のスタッフを既定にする。"""
    return process.verify(
        verifier_id=verifier_id if verifier_id is not None else StaffId.generate(),
        verified_at=VerificationTimestamp(datetime(2026, 8, 24, 2, 0, tzinfo=UTC)),
        result=VerificationResult.PASSED,
    )
