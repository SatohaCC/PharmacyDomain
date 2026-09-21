"""薬歴ユースケーステストで共有する組み立てヘルパー。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.medication_history import (
    AddFollowUpUseCase,
    AmendMedicationHistoryUseCase,
    FinalizeMedicationHistoryUseCase,
    GetCategoryCatalogUseCase,
    GetMedicationHistoryUseCase,
    GetPatientMedicalProfileUseCase,
    HandbookStatusInput,
    LabeledNoteInput,
    ListMedicationHistoriesByPatientUseCase,
    ProfileUpdateInput,
    RebuildPatientMedicalProfileUseCase,
    RecordTracingReportResponseUseCase,
    RecordTracingReportUseCase,
    ResidualDrugInput,
    SoapInput,
    StartMedicationHistoryCommand,
    StartMedicationHistoryUseCase,
    UpdateCategoryCatalogUseCase,
    UpdateMedicationHistoryDraftUseCase,
    VerifyStatutoryRecordUseCase,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing.dispensing_process import DispensingProcess
from app.domain.medication_history import (
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
    create_vendor_corporate_access_for,
)
from tests.factories.dispensing_factory import complete_dispensing, create_dispensing
from tests.factories.medication_history_factory import create_statutory_source
from tests.fakes.fake_clock import FakeClock
from tests.fakes.in_memory_medication_history_repository import (
    InMemoryMedicationHistoryCategoryCatalogRepository,
    InMemoryMedicationHistoryRepository,
)
from tests.fakes.in_memory_patient_medical_profile_repository import (
    InMemoryPatientMedicalProfileRepository,
)
from tests.fakes.medication_history_reference_boundaries import (
    FakeCounselorQualificationSource,
    FakeDispensingSource,
    FakeMedicationHistoryStoreReference,
    FakeStatutoryRecordSource,
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
    record_tracing_report: RecordTracingReportUseCase
    record_tracing_report_response: RecordTracingReportResponseUseCase
    record_repository: InMemoryMedicationHistoryRepository
    profile_repository: InMemoryPatientMedicalProfileRepository
    category_catalog_repository: InMemoryMedicationHistoryCategoryCatalogRepository
    corporate_repository: AutoProvisioningCorporateRepository
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


def create_fixture() -> MedicationHistoryFixture:
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
    corporate_access = create_vendor_corporate_access_for(corporate_repository)

    return MedicationHistoryFixture(
        start=StartMedicationHistoryUseCase(
            record_repository,
            corporate_access,
            store_reference,
            dispensing_source,
            staff_qualification,
            CounselorQualificationService(),
            clock,
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
            profile_repository,
            corporate_access,
            staff_qualification,
            CounselorQualificationService(),
            unit_of_work=NullUnitOfWork(),
        ),
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
        category_catalog_repository=category_catalog_repository,
        corporate_repository=corporate_repository,
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
    counselor_id: StaffId | None = None,
    dispensing: DispensingProcess | None = None,
    soap: SoapInput | None = None,
    residual_drug: ResidualDrugInput | None = None,
    handbook_status: HandbookStatusInput | None = None,
    profile_updates: ProfileUpdateInput | None = None,
) -> StartMedicationHistoryCommand:
    """薬歴作成コマンドを組み立てる。"""
    return StartMedicationHistoryCommand(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        dispensing_id=str(
            (dispensing if dispensing is not None else fixture.dispensing).id.value
        ),
        counselor_id=str(
            (counselor_id if counselor_id is not None else fixture.counselor_id).value
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
        profile_updates=profile_updates,
    )
