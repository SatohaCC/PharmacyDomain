"""永続化テストで使う集約のビルダー。

既存の factory が無い集約（患者・外部識別子・患者資格・資格選択履歴・頭書き）を
ここで組み立てる。DBなしの整合性テストと実DBの結合テストの両方から使う。
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from app.domain.claim import (
    ClaimCoverageBenefitRatio,
    ClaimCoverageCode,
    ClaimCoverageInsuredType,
    ClaimCoveragePriority,
    ClaimCoverageSymbol,
    ClaimInsurerNumber,
    ClaimPublicPayerNumber,
    ClaimPublicRecipientNumber,
    InsuranceCoverageSnapshot,
    PublicExpenseCoverageSnapshot,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.coverage.patient_coverage import PatientCoverage
from app.domain.coverage.primitives import (
    CoverageActivatedOn,
    CoverageActivation,
    CoverageDeactivatedOn,
    CoveragePeriod,
    CoveragePriority,
    CoverageType,
    CoverageValidFrom,
    CoverageValidTo,
    PublicExpenseCoverageDetails,
    PublicPayerNumber,
    PublicRecipientNumber,
)
from app.domain.medication_history.patient_medical_profile import PatientMedicalProfile
from app.domain.patient.external_identifier import PatientExternalIdentifier
from app.domain.patient.patient import Patient
from app.domain.patient.primitives import (
    ExternalPatientId,
    ExternalSystemName,
    PatientId,
    PatientNumber,
)
from app.domain.reception import (
    CoverageAppliedOn,
    CoverageRecordedAt,
    CoverageSelection,
    CoverageSelectionRecord,
    OperatorPrincipalId,
    SelectedInsuranceSource,
    SelectedPublicExpenseSource,
    SourceCoverageId,
)
from app.domain.store.primitives import StoreId
from tests.factories.staff_factory import create_person_names

APPLIED_ON = date(2026, 8, 23)
RECORDED_AT = datetime(2026, 8, 23, 1, 0, tzinfo=UTC)
VALID_FROM = date(2026, 8, 1)
VALID_TO = date(2026, 8, 31)


def create_patient(
    *,
    corporate_id: CorporateId | None = None,
    patient_number: int = 1,
    last_name: str = "佐藤",
    first_name: str = "花子",
) -> Patient:
    """テスト用の患者を作る。"""
    return Patient.create(
        corporate_id=corporate_id
        if corporate_id is not None
        else CorporateId.generate(),
        names=create_person_names(
            last_name=last_name,
            first_name=first_name,
            last_name_kana="サトウ",
            first_name_kana="ハナコ",
        ),
        patient_number=PatientNumber(patient_number),
    )


def create_external_identifier(
    *,
    corporate_id: CorporateId | None = None,
    patient_id: PatientId | None = None,
    system_name: str = "レセコンA",
    external_patient_id: str = "EXT-001",
) -> PatientExternalIdentifier:
    """テスト用の外部患者ID対応付けを作る。"""
    return PatientExternalIdentifier.create(
        corporate_id=corporate_id
        if corporate_id is not None
        else CorporateId.generate(),
        patient_id=patient_id if patient_id is not None else PatientId.generate(),
        system_name=ExternalSystemName(system_name),
        external_patient_id=ExternalPatientId(external_patient_id),
    )


def create_coverage(
    *,
    corporate_id: CorporateId | None = None,
    patient_id: PatientId | None = None,
    priority: int = 1,
    valid_from: date = VALID_FROM,
    valid_to: date | None = VALID_TO,
    deactivated_on: date | None = None,
) -> PatientCoverage:
    """テスト用の公費資格を作る。"""
    return PatientCoverage.create(
        corporate_id=corporate_id
        if corporate_id is not None
        else CorporateId.generate(),
        patient_id=patient_id if patient_id is not None else PatientId.generate(),
        coverage_type=CoverageType.PUBLIC_EXPENSE,
        period=CoveragePeriod(
            valid_from=CoverageValidFrom(valid_from),
            valid_to=CoverageValidTo(valid_to) if valid_to is not None else None,
        ),
        activation=CoverageActivation(
            activated_on=CoverageActivatedOn(valid_from),
            deactivated_on=(
                CoverageDeactivatedOn(deactivated_on)
                if deactivated_on is not None
                else None
            ),
        ),
        priority=CoveragePriority(priority),
        public_expense_details=PublicExpenseCoverageDetails(
            payer_number=PublicPayerNumber(f"1234567{priority}"),
            recipient_number=PublicRecipientNumber(f"123456{priority}"),
        ),
    )


def create_selection() -> CoverageSelection:
    """医療保険1件と第一公費1件からなる資格選択を作る。"""
    return CoverageSelection(
        insurance=SelectedInsuranceSource(
            source_coverage_id=SourceCoverageId.generate(),
            values=InsuranceCoverageSnapshot(
                insurer_number=ClaimInsurerNumber("01130012"),
                insured_symbol=ClaimCoverageSymbol("A"),
                insured_number=ClaimCoverageCode("456"),
                insured_type=ClaimCoverageInsuredType.SELF,
                benefit_ratio=ClaimCoverageBenefitRatio(70),
            ),
        ),
        public_expenses=(
            SelectedPublicExpenseSource(
                source_coverage_id=SourceCoverageId.generate(),
                values=PublicExpenseCoverageSnapshot(
                    priority=ClaimCoveragePriority(1),
                    payer_number=ClaimPublicPayerNumber("12345671"),
                    recipient_number=ClaimPublicRecipientNumber("1234561"),
                ),
            ),
        ),
    )


def create_selection_record(
    *,
    corporate_id: CorporateId | None = None,
    store_id: StoreId | None = None,
    patient_id: PatientId | None = None,
    applied_on: date = APPLIED_ON,
    recorded_at: datetime = RECORDED_AT,
) -> CoverageSelectionRecord:
    """テスト用の適用資格選択履歴を作る。"""
    return CoverageSelectionRecord.create(
        corporate_id=corporate_id
        if corporate_id is not None
        else CorporateId.generate(),
        store_id=store_id if store_id is not None else StoreId.generate(),
        patient_id=patient_id if patient_id is not None else PatientId.generate(),
        applied_on=CoverageAppliedOn(applied_on),
        selection=create_selection(),
        recorded_at=CoverageRecordedAt(recorded_at),
        recorded_by=OperatorPrincipalId("test-operator"),
    )


def create_medical_profile(
    *,
    corporate_id: CorporateId | None = None,
    patient_id: PatientId | None = None,
) -> PatientMedicalProfile:
    """テスト用の空の頭書きを作る。"""
    return PatientMedicalProfile.empty_for(
        corporate_id=corporate_id
        if corporate_id is not None
        else CorporateId.generate(),
        patient_id=patient_id if patient_id is not None else PatientId.generate(),
    )
