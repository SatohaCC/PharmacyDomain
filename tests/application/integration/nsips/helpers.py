"""NSIPS取込ユースケーステストで共有する組み立てヘルパー。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date

from app.application.composition.dispensing_references import (
    DispensingStaffQualificationAdapter,
    DispensingStoreReferenceAdapter,
    PrescriptionSourceAdapter,
)
from app.application.composition.medication_history_references import (
    CounselorQualificationAdapter,
    DispensingSourceAdapter,
    MedicationHistoryStoreReferenceAdapter,
)
from app.application.composition.prescription_references import (
    PrescriptionPatientReferenceAdapter,
    PrescriptionStoreReferenceAdapter,
)
from app.application.dispensing import (
    StartDispensingUseCase,
)
from app.application.integration.nsips.ingest_nsips import (
    IngestNsipsUseCase,
)
from app.application.integration.nsips.mapper import NsipsDataMapper
from app.application.integration.nsips.parser import NsipsParser
from app.application.medication_history import (
    AddFollowUpUseCase,
    ListMedicationHistoriesByPatientUseCase,
    StartMedicationHistoryUseCase,
)
from app.application.patient import (
    RegisterPatientExternalIdentifierUseCase,
    RegisterPatientUseCase,
)
from app.application.prescription import (
    ReadyForDispensingUseCase,
    RegisterPrescriptionUseCase,
)
from app.domain.corporate import CorporateId
from app.domain.dispensing import (
    DispensingConsistencyService,
    DispensingIterationUniquenessService,
    DispensingPharmacistService,
)
from app.domain.medication_history import (
    CounselorQualificationService,
)
from app.domain.prescription import (
    MedicineClassification,
    MedicineRestrictionFlag,
    NarcoticPrescriptionService,
    PrescriptionDocumentNumberUniquenessService,
    PublicExpenseBurdenService,
    RefillEligibilityService,
)
from app.domain.shared.medicine import (
    MedicineCode,
    MedicineCodeType,
    MedicineIdentifier,
)
from app.domain.staff import (
    AffiliationPeriod,
    PharmacistLicenseNumber,
    PharmacistProfile,
    StaffId,
    StaffQualifications,
    StoreAffiliation,
)
from app.domain.store import StoreId
from tests.application.access_helpers import (
    AutoProvisioningCorporateRepository,
    create_vendor_corporate_access_for,
)
from tests.factories.staff_factory import create_staff
from tests.factories.store_factory import create_store
from tests.fakes.fake_clock import FakeClock
from tests.fakes.in_memory_dispensing_process_repository import (
    InMemoryDispensingProcessRepository,
)
from tests.fakes.in_memory_medication_history_repository import (
    InMemoryMedicationHistoryRepository,
)
from tests.fakes.in_memory_patient_medical_profile_repository import (
    InMemoryPatientMedicalProfileRepository,
)
from tests.fakes.in_memory_patient_repository import (
    InMemoryPatientExternalIdentifierRepository,
    InMemoryPatientRepository,
)
from tests.fakes.in_memory_prescription_repository import (
    InMemoryPrescriptionRepository,
)
from tests.fakes.in_memory_staff_repository import (
    InMemoryStaffRepository,
)
from tests.fakes.in_memory_store_repository import (
    InMemoryStoreRepository,
)
from tests.fakes.null_unit_of_work import NullUnitOfWork
from tests.fakes.prescription_reference_boundaries import (
    FakeMedicineRestrictionSource,
    FakePublicExpenseAvailability,
)


def create_pharmacist_qualifications() -> StaffQualifications:
    """薬剤師資格を1つ持つ保有資格を組み立てる。"""
    return StaffQualifications.from_profiles(
        PharmacistProfile(license_number=PharmacistLicenseNumber("123456"))
    )


@dataclass(frozen=True, kw_only=True)
class NsipsFixture:
    """NSIPS取込テスト用Fixture。"""

    use_case: IngestNsipsUseCase
    corporate_id: CorporateId
    store_id: StoreId
    pharmacist_id: StaffId
    unqualified_staff_id: StaffId
    corporate_repo: AutoProvisioningCorporateRepository
    patient_repo: InMemoryPatientRepository
    patient_external_id_repo: InMemoryPatientExternalIdentifierRepository
    prescription_repo: InMemoryPrescriptionRepository
    dispensing_repo: InMemoryDispensingProcessRepository
    medication_history_repo: InMemoryMedicationHistoryRepository
    store_repo: InMemoryStoreRepository
    staff_repo: InMemoryStaffRepository
    medicine_restriction: FakeMedicineRestrictionSource
    unit_of_work: NullUnitOfWork
    clock: FakeClock


async def create_fixture() -> NsipsFixture:
    """NSIPS取込テストの事前条件一式を初期化して返す。"""
    corporate_id = CorporateId.generate()
    store_id = StoreId.generate()

    corporate_repo = AutoProvisioningCorporateRepository()
    corporate_access = create_vendor_corporate_access_for(corporate_repo)

    store_repo = InMemoryStoreRepository()
    store = create_store(corporate_id=corporate_id)
    # 明示的に指定したIDで配置
    store = replace(store, id=store_id)
    await store_repo.save(store)

    staff_repo = InMemoryStaffRepository()
    pharmacist = create_staff(
        corporate_id=corporate_id,
        qualifications=create_pharmacist_qualifications(),
    )
    pharmacist = replace(
        pharmacist,
        affiliations=(
            StoreAffiliation(
                store_id=store_id,
                is_primary=True,
                period=AffiliationPeriod(start_date=date(2026, 1, 1)),
            ),
        ),
    )
    await staff_repo.save(pharmacist)
    pharmacist_id = pharmacist.id

    unqualified_staff = create_staff(
        corporate_id=corporate_id,
        qualifications=None,
    )
    await staff_repo.save(unqualified_staff)
    unqualified_staff_id = unqualified_staff.id

    patient_repo = InMemoryPatientRepository()
    patient_external_id_repo = InMemoryPatientExternalIdentifierRepository()
    prescription_repo = InMemoryPrescriptionRepository()
    dispensing_repo = InMemoryDispensingProcessRepository()
    medication_history_repo = InMemoryMedicationHistoryRepository()
    profile_repo = InMemoryPatientMedicalProfileRepository()
    clock = FakeClock()
    unit_of_work = NullUnitOfWork()

    # 薬品マスタ
    medicine_restriction = FakeMedicineRestrictionSource()
    medicine_restriction.register(
        MedicineClassification(
            identifier=MedicineIdentifier(
                code_type=MedicineCodeType.RECEIPT,
                code=MedicineCode("610406001"),
            ),
            is_narcotic=MedicineRestrictionFlag.NO,
            has_dosage_limit=MedicineRestrictionFlag.NO,
            is_refill_restricted_patch=MedicineRestrictionFlag.NO,
        )
    )

    public_expense = FakePublicExpenseAvailability()

    # ユースケース組み立て
    register_patient = RegisterPatientUseCase(patient_repo, corporate_access)
    register_patient_ext = RegisterPatientExternalIdentifierUseCase(
        patient_repo, patient_external_id_repo, corporate_access
    )

    register_prescription = RegisterPrescriptionUseCase(
        repository=prescription_repo,
        corporate_access=corporate_access,
        store_reference=PrescriptionStoreReferenceAdapter(store_repo),
        patient_reference=PrescriptionPatientReferenceAdapter(patient_repo),
        medicine_restriction=medicine_restriction,
        public_expense_availability=public_expense,
        uniqueness_service=PrescriptionDocumentNumberUniquenessService(),
        narcotic_service=NarcoticPrescriptionService(),
        refill_service=RefillEligibilityService(),
        public_expense_service=PublicExpenseBurdenService(),
    )

    ready_for_dispensing = ReadyForDispensingUseCase(
        prescription_repo, corporate_access
    )

    start_dispensing = StartDispensingUseCase(
        repository=dispensing_repo,
        corporate_access=corporate_access,
        store_reference=DispensingStoreReferenceAdapter(store_repo),
        prescription_reference=PrescriptionSourceAdapter(prescription_repo),
        staff_qualification=DispensingStaffQualificationAdapter(staff_repo),
        consistency_service=DispensingConsistencyService(),
        uniqueness_service=DispensingIterationUniquenessService(),
        pharmacist_service=DispensingPharmacistService(),
        clock=clock,
    )

    start_medication_history = StartMedicationHistoryUseCase(
        repository=medication_history_repo,
        corporate_access=corporate_access,
        store_reference=MedicationHistoryStoreReferenceAdapter(store_repo),
        dispensing_reference=DispensingSourceAdapter(dispensing_repo),
        staff_qualification=CounselorQualificationAdapter(staff_repo),
        counselor_service=CounselorQualificationService(),
        clock=clock,
    )

    add_follow_up = AddFollowUpUseCase(
        repository=medication_history_repo,
        profile_repository=profile_repo,
        corporate_access=corporate_access,
        staff_qualification=CounselorQualificationAdapter(staff_repo),
        counselor_service=CounselorQualificationService(),
        unit_of_work=unit_of_work,
    )

    list_medication_histories = ListMedicationHistoriesByPatientUseCase(
        medication_history_repo, corporate_access
    )

    use_case = IngestNsipsUseCase(
        corporate_access=corporate_access,
        unit_of_work=unit_of_work,
        patient_external_id_repo=patient_external_id_repo,
        prescription_repo=prescription_repo,
        register_patient_use_case=register_patient,
        register_patient_external_id_use_case=register_patient_ext,
        register_prescription_use_case=register_prescription,
        ready_for_dispensing_use_case=ready_for_dispensing,
        start_dispensing_use_case=start_dispensing,
        start_medication_history_use_case=start_medication_history,
        add_follow_up_use_case=add_follow_up,
        list_medication_histories_use_case=list_medication_histories,
        parser=NsipsParser(),
        mapper=NsipsDataMapper(),
    )

    return NsipsFixture(
        use_case=use_case,
        corporate_id=corporate_id,
        store_id=store_id,
        pharmacist_id=pharmacist_id,
        unqualified_staff_id=unqualified_staff_id,
        corporate_repo=corporate_repo,
        patient_repo=patient_repo,
        patient_external_id_repo=patient_external_id_repo,
        prescription_repo=prescription_repo,
        dispensing_repo=dispensing_repo,
        medication_history_repo=medication_history_repo,
        store_repo=store_repo,
        staff_repo=staff_repo,
        medicine_restriction=medicine_restriction,
        unit_of_work=unit_of_work,
        clock=clock,
    )
