"""薬歴ユースケーステストで共有する組み立てヘルパー。"""

from __future__ import annotations

from dataclasses import dataclass, replace

from app.application.access_control.models import (
    ActorContext,
    ActorRole,
    ResolvedActorContext,
)
from app.application.access_control.policy import AuthorizationService
from app.application.composition.medication_history_references import (
    ReceptionMedicationHistorySourceAdapter,
)
from app.application.corporate.corporate_access import CorporateAccessService
from app.application.medication_history.add_follow_up import AddFollowUpUseCase
from app.application.medication_history.amend_medication_history import (
    AmendMedicationHistoryUseCase,
)
from app.application.medication_history.category_catalog import (
    GetCategoryCatalogUseCase,
    UpdateCategoryCatalogUseCase,
)
from app.application.medication_history.finalize_medication_history import (
    FinalizeMedicationHistoryUseCase,
)
from app.application.medication_history.get_medication_history import (
    GetMedicationHistoryUseCase,
    ListMedicationHistoriesByPatientUseCase,
)
from app.application.medication_history.get_patient_medical_profile import (
    GetPatientMedicalProfileUseCase,
    RebuildPatientMedicalProfileUseCase,
)
from app.application.medication_history.inputs import (
    BillingAdditionInput,
    HandbookStatusInput,
    LabeledNoteInput,
    ProfileUpdateInput,
    ResidualDrugInput,
    SoapInput,
)
from app.application.medication_history.record_tracing_report import (
    RecordTracingReportUseCase,
)
from app.application.medication_history.record_tracing_report_response import (
    RecordTracingReportResponseUseCase,
)
from app.application.medication_history.start_medication_history import (
    StartMedicationHistoryCommand,
    StartMedicationHistoryUseCase,
)
from app.application.medication_history.update_medication_history_draft import (
    UpdateMedicationHistoryDraftUseCase,
)
from app.application.medication_history.verify_statutory_record import (
    VerifyStatutoryRecordUseCase,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing.dispensing_process import DispensingProcess
from app.domain.identity.primitives import AccountPersonId, UserAccountId
from app.domain.medication_history.services import (
    CounselorQualificationService,
    StatutoryDispensingRecordService,
)
from app.domain.patient.primitives import PatientId
from app.domain.staff.primitives import (
    PharmacistLicenseNumber,
    PharmacistProfile,
    StaffId,
    StaffQualifications,
)
from app.domain.store.primitives import StoreId
from tests.application.access_helpers import (
    AutoProvisioningCorporateRepository,
)
from tests.factories.dispensing_factory import complete_dispensing, create_dispensing
from tests.factories.medication_history_factory import create_statutory_source
from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_medication_history_store_operations import (
    FakeMedicationHistoryStoreOperations,
)
from tests.fakes.in_memory_medication_history_repository import (
    InMemoryMedicationHistoryCategoryCatalogRepository,
    InMemoryMedicationHistoryRepository,
)
from tests.fakes.in_memory_patient_medical_profile_repository import (
    InMemoryPatientMedicalProfileRepository,
)
from tests.fakes.in_memory_reception_repository import InMemoryReceptionRepository
from tests.fakes.medication_history_reference_boundaries import (
    FakeCounselorQualificationSource,
    FakeDispensingSource,
    FakeMedicationHistoryStoreReference,
    FakeStatutoryRecordSource,
    InMemoryMedicationHistoryFollowUpSourceBoundary,
)
from tests.fakes.null_unit_of_work import NullUnitOfWork


def create_pharmacist_qualifications() -> StaffQualifications:
    """薬剤師資格を1つ持つ保有資格を組み立てる。"""
    return StaffQualifications.from_profiles(
        PharmacistProfile(license_number=PharmacistLicenseNumber("123456"))
    )


def create_soap_input(
    *,
    subjective: str = "飲み忘れは週に1回程度とのこと。",
    objective: str = "血圧手帳の記録は良好。",
    assessment: str = "アドヒアランスはおおむね良好。",
    plan: str = "次回まで服薬時刻の固定を提案。",
) -> SoapInput:
    """S/O/A/P がすべて埋まったSOAP入力を組み立てる。"""
    return SoapInput(
        subjective=(
            LabeledNoteInput(text=subjective, category="medication_adherence"),
        ),
        objective=(LabeledNoteInput(text=objective),),
        assessment=(LabeledNoteInput(text=assessment),),
        plan=(LabeledNoteInput(text=plan, category="future_plan_caution"),),
    )


@dataclass(frozen=True, kw_only=True)
class MedicationHistoryFixture:
    """ユースケース一式と、その依存へ手を入れるための参照。"""

    start: StartMedicationHistoryUseCase
    update_draft: UpdateMedicationHistoryDraftUseCase
    finalize: FinalizeMedicationHistoryUseCase
    amend: AmendMedicationHistoryUseCase
    get: GetMedicationHistoryUseCase
    list_by_patient: ListMedicationHistoriesByPatientUseCase
    get_profile: GetPatientMedicalProfileUseCase
    rebuild_profile: RebuildPatientMedicalProfileUseCase
    verify_statutory_record: VerifyStatutoryRecordUseCase
    get_category_catalog: GetCategoryCatalogUseCase
    update_category_catalog: UpdateCategoryCatalogUseCase
    add_follow_up: AddFollowUpUseCase
    store_operations: FakeMedicationHistoryStoreOperations
    follow_up_source_boundary: InMemoryMedicationHistoryFollowUpSourceBoundary
    record_tracing_report: RecordTracingReportUseCase
    record_tracing_report_response: RecordTracingReportResponseUseCase
    record_repository: InMemoryMedicationHistoryRepository
    profile_repository: InMemoryPatientMedicalProfileRepository
    reception_repository: InMemoryReceptionRepository
    category_catalog_repository: InMemoryMedicationHistoryCategoryCatalogRepository
    corporate_repository: AutoProvisioningCorporateRepository
    corporate_access: CorporateAccessService
    actor: ActorContext
    store_reference: FakeMedicationHistoryStoreReference
    dispensing_source: FakeDispensingSource
    staff_qualification: FakeCounselorQualificationSource
    statutory_source: FakeStatutoryRecordSource
    clock: FakeClock
    corporate_id: CorporateId
    store_id: StoreId
    patient_id: PatientId
    counselor_id: StaffId
    dispensing: DispensingProcess


def create_resolved_actor(
    *,
    staff_id: StaffId | None,
    role: ActorRole = ActorRole.VENDOR_SYSTEM_ADMIN,
    corporate_id: CorporateId | None = None,
    store_ids: frozenset[StoreId] = frozenset(),
) -> ResolvedActorContext:
    """信頼済みのテストActorをスタッフ解決状態つきで生成する。"""
    return ResolvedActorContext(
        principal_id="test-pharmacist-actor",
        roles=frozenset({role}),
        corporate_id=corporate_id,
        person_id=AccountPersonId.generate(),
        account_id=UserAccountId.generate(),
        staff_id=staff_id,
        store_ids=store_ids,
    )


def create_fixture(
    *,
    actor: ActorContext | None = None,
    store_role: ActorRole | None = None,
    additional_store_ids: frozenset[StoreId] = frozenset(),
) -> MedicationHistoryFixture:
    """既定の依存を配線した Fixture を生成する。"""
    corporate_id = CorporateId.generate()
    store_id = StoreId.generate()
    patient_id = PatientId.generate()
    counselor_id = StaffId.generate()
    dispensing = complete_dispensing(
        create_dispensing(
            corporate_id=corporate_id, store_id=store_id, patient_id=patient_id
        )
    )

    record_repository = InMemoryMedicationHistoryRepository()
    profile_repository = InMemoryPatientMedicalProfileRepository()
    reception_repository = InMemoryReceptionRepository()
    category_catalog_repository = InMemoryMedicationHistoryCategoryCatalogRepository()
    store_reference = FakeMedicationHistoryStoreReference()
    store_reference.register(corporate_id=corporate_id, store_id=store_id)
    dispensing_source = FakeDispensingSource()
    dispensing_source.register(dispensing)
    staff_qualification = FakeCounselorQualificationSource()
    staff_qualification.register(
        corporate_id=corporate_id,
        staff_id=counselor_id,
        qualifications=create_pharmacist_qualifications(),
    )
    statutory_source = FakeStatutoryRecordSource()
    statutory_source.register(
        corporate_id=corporate_id,
        source=create_statutory_source(
            patient_id=patient_id,
            prescription_id=dispensing.prescription_id,
            pharmacist_ids=(dispensing.dispenser_id, counselor_id),
        ),
    )
    clock = FakeClock()
    corporate_repository = AutoProvisioningCorporateRepository()
    store_operations = FakeMedicationHistoryStoreOperations()
    follow_up_source_boundary = InMemoryMedicationHistoryFollowUpSourceBoundary(
        record_repository
    )
    resolved_actor = actor or create_resolved_actor(
        staff_id=counselor_id,
        role=store_role or ActorRole.VENDOR_SYSTEM_ADMIN,
        corporate_id=corporate_id if store_role is not None else None,
        store_ids=(
            frozenset({store_id}) | additional_store_ids
            if store_role is not None
            else frozenset()
        ),
    )
    corporate_access = CorporateAccessService(
        corporate_repository, AuthorizationService(resolved_actor)
    )

    return MedicationHistoryFixture(
        start=StartMedicationHistoryUseCase(
            record_repository,
            corporate_access,
            store_reference,
            dispensing_source,
            staff_qualification,
            CounselorQualificationService(),
            NullUnitOfWork(),
            ReceptionMedicationHistorySourceAdapter(reception_repository),
        ),
        update_draft=UpdateMedicationHistoryDraftUseCase(
            record_repository, corporate_access
        ),
        finalize=FinalizeMedicationHistoryUseCase(
            record_repository,
            profile_repository,
            corporate_access,
            NullUnitOfWork(),
            category_catalog_repository=category_catalog_repository,
            staff_qualification=staff_qualification,
            counselor_service=CounselorQualificationService(),
            clock=clock,
        ),
        amend=AmendMedicationHistoryUseCase(
            record_repository,
            corporate_access,
            staff_qualification,
            CounselorQualificationService(),
            clock,
        ),
        get=GetMedicationHistoryUseCase(record_repository, corporate_access),
        list_by_patient=ListMedicationHistoriesByPatientUseCase(
            record_repository, corporate_access
        ),
        get_profile=GetPatientMedicalProfileUseCase(
            profile_repository, corporate_access
        ),
        rebuild_profile=RebuildPatientMedicalProfileUseCase(
            record_repository, profile_repository, corporate_access
        ),
        verify_statutory_record=VerifyStatutoryRecordUseCase(
            record_repository,
            corporate_access,
            dispensing_source,
            statutory_source,
            StatutoryDispensingRecordService(),
        ),
        get_category_catalog=GetCategoryCatalogUseCase(
            category_catalog_repository, corporate_access
        ),
        update_category_catalog=UpdateCategoryCatalogUseCase(
            category_catalog_repository, corporate_access
        ),
        add_follow_up=AddFollowUpUseCase(
            record_repository,
            corporate_access,
            staff_qualification,
            CounselorQualificationService(),
            NullUnitOfWork(),
            store_operations,
            follow_up_source_boundary,
        ),
        store_operations=store_operations,
        follow_up_source_boundary=follow_up_source_boundary,
        record_tracing_report=RecordTracingReportUseCase(
            record_repository,
            corporate_access,
            staff_qualification,
            CounselorQualificationService(),
        ),
        record_tracing_report_response=RecordTracingReportResponseUseCase(
            record_repository,
            corporate_access,
        ),
        record_repository=record_repository,
        profile_repository=profile_repository,
        reception_repository=reception_repository,
        category_catalog_repository=category_catalog_repository,
        corporate_repository=corporate_repository,
        corporate_access=corporate_access,
        actor=resolved_actor,
        store_reference=store_reference,
        dispensing_source=dispensing_source,
        staff_qualification=staff_qualification,
        statutory_source=statutory_source,
        clock=clock,
        corporate_id=corporate_id,
        store_id=store_id,
        patient_id=patient_id,
        counselor_id=counselor_id,
        dispensing=dispensing,
    )


def register_another_dispensing(
    fixture: MedicationHistoryFixture,
) -> DispensingProcess:
    """同一患者の別の調剤セッションを作って境界へ登録する。

    同一調剤に確定済の薬歴は1件までなので、2件目の薬歴には別の調剤が要る。
    """
    another = create_dispensing(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        patient_id=fixture.patient_id,
    )
    fixture.dispensing_source.register(another)
    return another


def create_start_command(
    fixture: MedicationHistoryFixture,
    *,
    dispensing: DispensingProcess | None = None,
    soap: SoapInput | None = None,
    residual_drug: ResidualDrugInput | None = None,
    handbook_status: HandbookStatusInput | None = None,
    profile_updates: ProfileUpdateInput | None = None,
    information_sheet_provided: bool | None = False,
    billing_additions: tuple[BillingAdditionInput, ...] | None = None,
    source_system: str | None = None,
) -> StartMedicationHistoryCommand:
    """薬歴作成コマンドを組み立てる。"""
    return StartMedicationHistoryCommand(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        dispensing_id=str(
            (dispensing if dispensing is not None else fixture.dispensing).id.value
        ),
        method="face_to_face",
        soap=soap if soap is not None else create_soap_input(),
        handbook_status=(
            handbook_status
            if handbook_status is not None
            else HandbookStatusInput(presented=True)
        ),
        residual_drug=(
            residual_drug
            if residual_drug is not None
            else ResidualDrugInput(has_residual_drugs=False)
        ),
        information_sheet_provided=information_sheet_provided,
        profile_updates=profile_updates,
        billing_additions=billing_additions,
        source_system=source_system,
    )


def create_nsips_start_command(
    fixture: MedicationHistoryFixture,
) -> StartMedicationHistoryCommand:
    """NSIPS由来の初回薬歴コマンドを作る。"""
    return replace(
        create_start_command(fixture),
        source_system="NSIPS",
        imported_at=fixture.clock.now(),
    )
