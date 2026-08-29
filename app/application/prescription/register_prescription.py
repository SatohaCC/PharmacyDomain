"""処方箋を受け付けて登録するユースケース。

**麻薬・リフィルを含む処方箋はマスタが揃うまで登録できない。** 判定に必要な
医薬品マスタが本システムに無いため、``MedicineRestrictionBoundary`` は
``UNKNOWN`` を返し、Domain Service がそれを拒否する（fail-closed）。
「マスタが無いので該当しない」と黙って通す実装にはしない。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.application.access_control import CorporateAccessBoundary, Permission
from app.application.prescription.get_prescription import PrescriptionDto
from app.application.prescription.inputs import (
    DepartmentInput,
    MedicalInstitutionInput,
    PrescriberInput,
    PrescriptionManagementInput,
    RpInput,
)
from app.application.prescription.reference import (
    MedicineRestrictionBoundary,
    PatientReferenceBoundary,
    PublicExpenseAvailabilityBoundary,
    StoreReferenceBoundary,
)
from app.application.prescription.support import (
    build_department,
    build_management_info,
    build_medical_institution,
    build_period,
    build_prescriber,
    build_rps,
    parse_source_type,
    to_optional_text,
)
from app.base.domain.medicine import PublicExpenseBurden
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientId
from app.domain.prescription import (
    NarcoticPrescriptionService,
    Prescription,
    PrescriptionDocumentNumber,
    PrescriptionDocumentNumberUniquenessService,
    PrescriptionRepository,
    PublicExpenseBurdenService,
    RefillEligibilityService,
)
from app.domain.reception.primitives import CoverageSelectionRecordId
from app.domain.store.primitives import StoreId


@dataclass(frozen=True, kw_only=True)
class RegisterPrescriptionCommand:
    """処方箋登録の入力データ。認可Actorは含めない。"""

    corporate_id: str
    store_id: str
    patient_id: str
    source_type: str
    document_number: str
    issued_date: date
    medical_institution: MedicalInstitutionInput
    department: DepartmentInput
    prescriber: PrescriberInput
    rps: tuple[RpInput, ...]
    valid_to: date | None = None
    management_info: PrescriptionManagementInput | None = None
    coverage_selection_record_id: str | None = None


class RegisterPrescriptionUseCase:
    """法人・店舗・患者の境界を確認して処方箋を登録する。"""

    def __init__(
        self,
        repository: PrescriptionRepository,
        corporate_access: CorporateAccessBoundary,
        store_reference: StoreReferenceBoundary,
        patient_reference: PatientReferenceBoundary,
        medicine_restriction: MedicineRestrictionBoundary,
        public_expense_availability: PublicExpenseAvailabilityBoundary,
        uniqueness_service: PrescriptionDocumentNumberUniquenessService,
        narcotic_service: NarcoticPrescriptionService,
        refill_service: RefillEligibilityService,
        public_expense_service: PublicExpenseBurdenService,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access
        self._store_reference = store_reference
        self._patient_reference = patient_reference
        self._medicine_restriction = medicine_restriction
        self._public_expense_availability = public_expense_availability
        self._uniqueness_service = uniqueness_service
        self._narcotic_service = narcotic_service
        self._refill_service = refill_service
        self._public_expense_service = public_expense_service

    async def execute(self, command: RegisterPrescriptionCommand) -> PrescriptionDto:
        """境界と集約外の不変条件を確認して処方箋を保存する。"""
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.MANAGE_PRESCRIPTION,
        )
        store_id = StoreId.parse(command.store_id)
        await self._store_reference.require_exists(
            corporate_id=corporate_id,
            store_id=store_id,
        )
        patient_id = PatientId.parse(command.patient_id)
        await self._patient_reference.require_exists(
            corporate_id=corporate_id,
            patient_id=patient_id,
        )
        record_id = self._parse_record_id(command.coverage_selection_record_id)
        prescription = Prescription.create(
            corporate_id=corporate_id,
            store_id=store_id,
            patient_id=patient_id,
            source_type=parse_source_type(command.source_type),
            document_number=PrescriptionDocumentNumber(command.document_number),
            medical_institution=build_medical_institution(command.medical_institution),
            department=build_department(command.department),
            prescriber=build_prescriber(command.prescriber),
            period=build_period(
                issued_date=command.issued_date, valid_to=command.valid_to
            ),
            rps=build_rps(command.rps),
            management_info=build_management_info(command.management_info),
            coverage_selection_record_id=record_id,
        )
        await self._verify_medicine_restrictions(prescription)
        await self._verify_public_expense_burden(prescription, record_id=record_id)
        await self._verify_document_number_is_unique(prescription)
        await self._repository.save(prescription)
        return PrescriptionDto.from_entity(prescription)

    @staticmethod
    def _parse_record_id(raw: str | None) -> CoverageSelectionRecordId | None:
        """資格選択履歴IDを変換する。空文字は未指定として扱う。"""
        value = to_optional_text(raw)
        if value is None:
            return None
        return CoverageSelectionRecordId.parse(value)

    async def _verify_medicine_restrictions(self, prescription: Prescription) -> None:
        """麻薬（#5）とリフィル適用除外（#6）を医薬品マスタ由来の事実で検証する。

        マスタは**処方箋の交付日**で引く。麻薬指定も経過措置期限も時点で
        変わるため、登録処理を実行した日ではなく、その処方箋が書かれた日の
        マスタで判定しなければ過去の処方を誤判定する。
        """
        classifications = await self._medicine_restriction.classify(
            identifiers=prescription.medicine_identifiers,
            as_of=prescription.period.issued_date.value,
        )
        self._narcotic_service.ensure_narcotic_details_present(
            prescription, classifications
        )
        self._refill_service.ensure_refill_allowed(prescription, classifications)

    async def _verify_public_expense_burden(
        self,
        prescription: Prescription,
        *,
        record_id: CoverageSelectionRecordId | None,
    ) -> None:
        """公費負担区分に患者資格の裏付けがあることを検証する（#7）。

        資格選択履歴が紐付いていない処方箋は、裏付けの取りようが無いので
        「どの公費枠も存在しない」として検証する。空の枠を渡すことで、
        負担ありの薬品があれば Domain Service が拒否する（fail-closed）。
        履歴の有無で検証を飛ばす分岐にすると、履歴を付けないだけで
        裏付けの無い公費負担が通ってしまう。
        """
        if record_id is None:
            available = PublicExpenseBurden()
        else:
            available = await self._public_expense_availability.available_burden(
                corporate_id=prescription.corporate_id,
                patient_id=prescription.patient_id,
                coverage_selection_record_id=record_id,
            )
        self._public_expense_service.ensure_burden_is_covered(prescription, available)

    async def _verify_document_number_is_unique(
        self, prescription: Prescription
    ) -> None:
        """電子処方箋の引換番号が法人内で重複しないことを事前に確認する。

        これは早期エラー用であり、原子性の担保は ``save()`` の契約側にある。
        判定は同じ Domain Service を呼び、規則の実装を2箇所に分けない。
        """
        existing = await self._repository.get_by_document_number(
            corporate_id=prescription.corporate_id,
            document_number=prescription.document_number,
        )
        self._uniqueness_service.ensure_no_conflict(
            prescription, [] if existing is None else [existing]
        )
