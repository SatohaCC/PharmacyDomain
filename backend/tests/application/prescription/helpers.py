"""処方箋ユースケーステストで共有する組み立てヘルパー。

``RegisterPrescriptionCommand`` は剤（Rp）→薬品明細と2段の入れ子を持ち、
依存も10個ある。各テストで丸ごと組み立てると Arrange が読めなくなるため、
既定値を持つファクトリと、依存へ手を入れられる Fixture をここに集約する。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.application.access_control.boundary_models import (
    ActorContext,
    ActorRole,
    ResolvedActorContext,
)
from app.application.access_control.policies import AuthorizationService
from app.application.corporate.commands.services.corporate_access import (
    CorporateAccessService,
)
from app.application.prescription.commands.audit_drug_interactions import (
    AuditDrugInteractionsUseCase,
)
from app.application.prescription.commands.cancel_prescription import (
    CancelPrescriptionUseCase,
)
from app.application.prescription.commands.models import (
    DepartmentInput,
    DosageInstructionInput,
    MedicalInstitutionInput,
    MedicineInput,
    PrescriberInput,
    PrescriptionManagementInput,
    PublicExpenseBurdenInput,
    RegisterPrescriptionCommand,
    RpInput,
)
from app.application.prescription.commands.ready_for_dispensing import (
    ReadyForDispensingUseCase,
)
from app.application.prescription.commands.register_prescription import (
    RegisterPrescriptionUseCase,
)
from app.application.prescription.commands.resolve_inquiry import ResolveInquiryUseCase
from app.application.prescription.commands.start_inquiry import StartInquiryUseCase
from app.application.prescription.queries.get_prescription import GetPrescriptionUseCase
from app.domain.corporate.identifiers import CorporateId
from app.domain.patient.identifiers import PatientId
from app.domain.prescription.primitives import (
    MedicineCode,
    MedicineCodeType,
    MedicineRestrictionFlag,
)
from app.domain.prescription.services import (
    InquiryPharmacistService,
    NarcoticPrescriptionService,
    PrescriptionDocumentNumberUniquenessService,
    PublicExpenseBurdenService,
    RefillEligibilityService,
)
from app.domain.prescription.value_objects import (
    MedicineClassification,
    MedicineIdentifier,
)
from app.domain.shared.actor import AccountPersonId, UserAccountId
from app.domain.staff.identifiers import StaffId
from app.domain.staff.primitives import PharmacistLicenseNumber
from app.domain.staff.value_objects import PharmacistProfile, StaffQualifications
from app.domain.store.identifiers import StoreId
from app.infrastructure.readers.prescription_get_prescription import (
    GetPrescriptionProjection,
)
from tests.application.access_helpers import (
    AutoProvisioningCorporateRepository,
)
from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_drug_interaction import FakeDrugInteractionDataSource
from tests.fakes.in_memory_prescription_repository import (
    InMemoryPrescriptionRepository,
)
from tests.fakes.prescription_reference_boundaries import (
    FakeMedicineRestrictionSource,
    FakePrescriptionPatientReference,
    FakePrescriptionStoreReference,
    FakePublicExpenseAvailability,
    FakeStaffQualificationSource,
)

ISSUED_ON = date(2026, 8, 24)
VALID_TO = date(2026, 8, 27)
DOCUMENT_NUMBER = "1234567890123456"
MEDICINE_CODE = "2171022F1029"
MEDICINE_NAME = "ノルバスク錠２．５ｍｇ"

#: 既定の薬品識別子。医薬品マスタへの登録キーになる。
DEFAULT_IDENTIFIER = MedicineIdentifier(
    code_type=MedicineCodeType.YJ,
    code=MedicineCode(MEDICINE_CODE),
)


def create_medicine_input(
    *,
    line_number: int = 1,
    code: str | None = MEDICINE_CODE,
    code_type: str = MedicineCodeType.YJ.value,
    name: str = MEDICINE_NAME,
    amount: str = "3",
    unit: str = "錠",
    public_expense_burden: PublicExpenseBurdenInput | None = None,
) -> MedicineInput:
    """処方薬品1明細の入力を組み立てる。"""
    return MedicineInput(
        line_number=line_number,
        code_type=code_type,
        code=code,
        name=name,
        amount=amount,
        unit=unit,
        public_expense_burden=public_expense_burden,
    )


def create_rp_input(
    *,
    rp_number: int = 1,
    category: str = "internal",
    quantity: int = 14,
    medicines: tuple[MedicineInput, ...] | None = None,
) -> RpInput:
    """剤（Rp）の入力を組み立てる。"""
    return RpInput(
        rp_number=rp_number,
        category=category,
        quantity=quantity,
        dosage_instruction=DosageInstructionInput(
            code_type="none",
            name="1日3回毎食後",
        ),
        medicines=medicines if medicines is not None else (create_medicine_input(),),
    )


def create_register_command(
    *,
    corporate_id: CorporateId,
    store_id: StoreId,
    patient_id: PatientId,
    source_type: str = "paper_qr",
    document_number: str = DOCUMENT_NUMBER,
    rps: tuple[RpInput, ...] | None = None,
    valid_to: date | None = VALID_TO,
    management_info: PrescriptionManagementInput | None = None,
    coverage_selection_record_id: str | None = None,
) -> RegisterPrescriptionCommand:
    """処方箋登録コマンドを組み立てる。"""
    return RegisterPrescriptionCommand(
        corporate_id=str(corporate_id.value),
        store_id=str(store_id.value),
        patient_id=str(patient_id.value),
        source_type=source_type,
        document_number=document_number,
        issued_date=ISSUED_ON,
        valid_to=valid_to,
        medical_institution=MedicalInstitutionInput(
            code_type="medical",
            code="1234567",
            prefecture_code="13",
            name="医療法人 サンプル病院",
        ),
        department=DepartmentInput(code_type="none", name="内科"),
        prescriber=PrescriberInput(
            last_name="佐藤",
            first_name="一郎",
            last_name_kana="サトウ",
            first_name_kana="イチロウ",
        ),
        rps=rps if rps is not None else (create_rp_input(),),
        management_info=management_info,
        coverage_selection_record_id=coverage_selection_record_id,
    )


def create_classification(
    *,
    identifier: MedicineIdentifier = DEFAULT_IDENTIFIER,
    is_narcotic: MedicineRestrictionFlag = MedicineRestrictionFlag.NO,
    has_dosage_limit: MedicineRestrictionFlag = MedicineRestrictionFlag.NO,
    is_refill_restricted_patch: MedicineRestrictionFlag = MedicineRestrictionFlag.NO,
) -> MedicineClassification:
    """医薬品マスタ1件分の規制区分を組み立てる。"""
    return MedicineClassification(
        identifier=identifier,
        is_narcotic=is_narcotic,
        has_dosage_limit=has_dosage_limit,
        is_refill_restricted_patch=is_refill_restricted_patch,
    )


def create_pharmacist_qualifications() -> StaffQualifications:
    """薬剤師資格を1つ持つ保有資格を組み立てる。"""
    return StaffQualifications.from_profiles(
        PharmacistProfile(license_number=PharmacistLicenseNumber("123456"))
    )


@dataclass(frozen=True, kw_only=True)
class PrescriptionFixture:
    """ユースケース一式と、その依存へ手を入れるための参照。"""

    register: RegisterPrescriptionUseCase
    start_inquiry: StartInquiryUseCase
    resolve_inquiry: ResolveInquiryUseCase
    ready_for_dispensing: ReadyForDispensingUseCase
    cancel: CancelPrescriptionUseCase
    get: GetPrescriptionUseCase
    audit_interactions: AuditDrugInteractionsUseCase
    interaction_data_source: FakeDrugInteractionDataSource
    repository: InMemoryPrescriptionRepository
    corporate_repository: AutoProvisioningCorporateRepository
    store_reference: FakePrescriptionStoreReference
    patient_reference: FakePrescriptionPatientReference
    staff_qualification: FakeStaffQualificationSource
    medicine_restriction: FakeMedicineRestrictionSource
    public_expense: FakePublicExpenseAvailability
    clock: FakeClock
    corporate_id: CorporateId
    store_id: StoreId
    patient_id: PatientId
    pharmacist_id: StaffId


def create_resolved_actor(
    *,
    staff_id: StaffId | None,
    role: ActorRole = ActorRole.VENDOR_SYSTEM_ADMIN,
    corporate_id: CorporateId | None = None,
    store_ids: frozenset[StoreId] = frozenset(),
) -> ResolvedActorContext:
    """信頼済みのテストActorをスタッフ解決状態つきで生成する。"""
    return ResolvedActorContext(
        principal_id="test-prescription-actor",
        roles=frozenset({role}),
        corporate_id=corporate_id,
        person_id=AccountPersonId.generate(),
        account_id=UserAccountId.generate(),
        staff_id=staff_id,
        store_ids=store_ids,
    )


def create_fixture(
    *,
    register_medicine: bool = True,
    as_corporate_admin: bool = False,
    actor: ActorContext | None = None,
) -> PrescriptionFixture:
    """既定の依存を配線した Fixture を生成する。

    Args:
        register_medicine: 既定の薬品を医薬品マスタへ登録するか。``False`` に
            すると「マスタ未登録」の状態を再現できる。
        as_corporate_admin: 操作主体を自法人の法人管理者にするか。``False`` の
            ときはベンダーシステム管理者。処方箋の権限が法人管理者にも
            与えられていることを、この切り替えで確かめられる。
    """
    corporate_id = CorporateId.generate()
    store_id = StoreId.generate()
    patient_id = PatientId.generate()
    pharmacist_id = (
        actor.staff_id
        if isinstance(actor, ResolvedActorContext) and actor.staff_id is not None
        else StaffId.generate()
    )

    repository = InMemoryPrescriptionRepository()
    store_reference = FakePrescriptionStoreReference()
    store_reference.register(corporate_id=corporate_id, store_id=store_id)
    patient_reference = FakePrescriptionPatientReference()
    patient_reference.register(corporate_id=corporate_id, patient_id=patient_id)
    staff_qualification = FakeStaffQualificationSource()
    staff_qualification.register(
        corporate_id=corporate_id,
        staff_id=pharmacist_id,
        qualifications=create_pharmacist_qualifications(),
    )
    medicine_restriction = FakeMedicineRestrictionSource()
    if register_medicine:
        medicine_restriction.register(create_classification())
    public_expense = FakePublicExpenseAvailability()
    clock = FakeClock()
    corporate_repository = AutoProvisioningCorporateRepository()
    resolved_actor = actor or (
        create_resolved_actor(
            staff_id=pharmacist_id,
            role=ActorRole.CORPORATE_ADMIN,
            corporate_id=corporate_id,
            store_ids=frozenset({store_id}),
        )
        if as_corporate_admin
        else create_resolved_actor(staff_id=pharmacist_id)
    )
    corporate_access = CorporateAccessService(
        corporate_repository,
        AuthorizationService(resolved_actor),
    )

    return PrescriptionFixture(
        register=RegisterPrescriptionUseCase(
            repository,
            corporate_access,
            store_reference,
            patient_reference,
            medicine_restriction,
            public_expense,
            PrescriptionDocumentNumberUniquenessService(),
            NarcoticPrescriptionService(),
            RefillEligibilityService(),
            PublicExpenseBurdenService(),
        ),
        start_inquiry=StartInquiryUseCase(
            repository,
            corporate_access,
            staff_qualification,
            InquiryPharmacistService(),
            clock,
        ),
        resolve_inquiry=ResolveInquiryUseCase(
            repository,
            corporate_access,
            clock,
            staff_qualification=staff_qualification,
            pharmacist_service=InquiryPharmacistService(),
        ),
        ready_for_dispensing=ReadyForDispensingUseCase(repository, corporate_access),
        cancel=CancelPrescriptionUseCase(repository, corporate_access),
        get=GetPrescriptionUseCase(
            reader=GetPrescriptionProjection(repository),
            corporate_access=corporate_access,
        ),
        audit_interactions=AuditDrugInteractionsUseCase(
            authorization_service=AuthorizationService(corporate_access.actor),
            data_source=FakeDrugInteractionDataSource(),
        ),
        interaction_data_source=FakeDrugInteractionDataSource(),
        repository=repository,
        corporate_repository=corporate_repository,
        store_reference=store_reference,
        patient_reference=patient_reference,
        staff_qualification=staff_qualification,
        medicine_restriction=medicine_restriction,
        public_expense=public_expense,
        clock=clock,
        corporate_id=corporate_id,
        store_id=store_id,
        patient_id=patient_id,
        pharmacist_id=pharmacist_id,
    )
