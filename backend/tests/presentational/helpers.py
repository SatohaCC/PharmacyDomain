"""プレゼンテーション層テスト用のユースケース束。

HTTPの結線だけを確かめたいので、PostgreSQLのスコープは通さず、インメモリ
Repositoryで組んだ本物のユースケースを束へ入れて差し替える。認可の判定そのものは
Application層のテストが確かめているため、ここでは固定の主体を使う。
"""

from __future__ import annotations

from app.application.access_control.boundary_models import (
    ActorContext,
    ActorRole,
    ResolvedActorContext,
)
from app.application.access_control.policies import AuthorizationService
from app.application.common.clock import Clock
from app.application.composition.adapters.coverage_references import (
    CoveragePatientReferenceAdapter,
    CoverageStoreReferenceAdapter,
)
from app.application.composition.adapters.effective_policy_resolver import (
    EffectivePolicyResolver,
)
from app.application.composition.adapters.organization_snapshot_mapping import (
    ManagerStaffAdapter,
    StaffStoreAdapter,
)
from app.application.composition.adapters.reception_medication_history import (
    ReceptionMedicationHistoryAssociationAdapter,
)
from app.application.composition.adapters.staff_account_registration import (
    StaffAccountRegistrationAdapter,
)
from app.application.composition.adapters.staff_person_adapter import StaffPersonAdapter
from app.application.composition.registry import (
    CorporateUseCases,
    CoverageUseCases,
    MedicineCatalogUseCases,
    PatientUseCases,
    ReceptionUseCases,
    StaffUseCases,
    StoreUseCases,
)
from app.application.corporate.commands.change_corporate_name import (
    ChangeCorporateNameUseCase,
)
from app.application.corporate.commands.change_corporate_status import (
    ChangeCorporateStatusUseCase,
)
from app.application.corporate.commands.change_representative import (
    ChangeRepresentativeUseCase,
)
from app.application.corporate.commands.register_corporate import (
    RegisterCorporateUseCase,
)
from app.application.corporate.commands.services.corporate_access import (
    CorporateAccessService,
)
from app.application.corporate.commands.update_corporate_details import (
    UpdateCorporateDetailsUseCase,
)
from app.application.corporate.commands.update_corporate_policy import (
    UpdateCorporatePolicyUseCase,
)
from app.application.corporate.queries.get_corporate import GetCorporateUseCase
from app.application.corporate.queries.list_corporates import ListCorporatesUseCase
from app.application.coverage.commands.change_patient_coverage_period import (
    ChangePatientCoveragePeriodUseCase,
)
from app.application.coverage.commands.deactivate_patient_coverage import (
    DeactivatePatientCoverageUseCase,
)
from app.application.coverage.commands.record_coverage_selection import (
    RecordCoverageSelectionUseCase,
)
from app.application.coverage.commands.register_patient_coverage import (
    RegisterPatientCoverageUseCase,
)
from app.application.coverage.commands.services.selection import (
    CoverageSelectionBuilder,
)
from app.application.coverage.queries.get_last_coverage_selection import (
    GetLastCoverageSelectionUseCase,
)
from app.application.coverage.queries.get_patient_coverage import (
    GetPatientCoverageUseCase,
)
from app.application.coverage.queries.list_patient_coverages import (
    ListPatientCoveragesUseCase,
)
from app.application.medicine_catalog.commands.import_yj_catalog import (
    ImportYjCatalogUseCase,
)
from app.application.medicine_catalog.commands.register_medicine import (
    RegisterMedicineUseCase,
)
from app.application.medicine_catalog.queries.get_effective_medicine import (
    GetEffectiveMedicineUseCase,
)
from app.application.patient.commands.change_patient_birth_date import (
    ChangePatientBirthDateUseCase,
)
from app.application.patient.commands.change_patient_heading import (
    ChangePatientHeadingUseCase,
)
from app.application.patient.commands.change_patient_names import (
    ChangePatientNamesUseCase,
)
from app.application.patient.commands.change_patient_profile import (
    ChangePatientProfileUseCase,
)
from app.application.patient.commands.deactivate_patient import DeactivatePatientUseCase
from app.application.patient.commands.deactivate_patient_external_identifier import (
    DeactivatePatientExternalIdentifierUseCase,
)
from app.application.patient.commands.merge_patients import MergePatientsUseCase
from app.application.patient.commands.reactivate_patient import ReactivatePatientUseCase
from app.application.patient.commands.register_patient import RegisterPatientUseCase
from app.application.patient.commands.register_patient_external_identifier import (
    RegisterPatientExternalIdentifierUseCase,
)
from app.application.patient.queries.get_patient import GetPatientUseCase
from app.application.patient.queries.get_patient_external_identifier import (
    GetPatientExternalIdentifierUseCase,
)
from app.application.patient.queries.get_patient_heading import GetPatientHeadingUseCase
from app.application.patient.queries.list_patient_external_identifiers import (
    ListPatientExternalIdentifiersUseCase,
)
from app.application.reception.commands.associate_reception_medication_history import (
    AssociateReceptionMedicationHistoryUseCase,
)
from app.application.staff.commands.activate_staff import ActivateStaffUseCase
from app.application.staff.commands.assign_staff_concurrent_store import (
    AssignStaffConcurrentStoreUseCase,
)
from app.application.staff.commands.change_staff_job_title import (
    ChangeStaffJobTitleUseCase,
)
from app.application.staff.commands.change_staff_names import ChangeStaffNamesUseCase
from app.application.staff.commands.deactivate_staff import DeactivateStaffUseCase
from app.application.staff.commands.manage_staff_leave import (
    ReturnStaffFromLeaveUseCase,
    StartStaffLeaveUseCase,
)
from app.application.staff.commands.register_staff import RegisterStaffUseCase
from app.application.staff.commands.remove_staff_concurrent_store import (
    RemoveStaffConcurrentStoreUseCase,
)
from app.application.staff.commands.transfer_staff_home_store import (
    TransferStaffHomeStoreUseCase,
)
from app.application.staff.commands.update_staff_employment import (
    UpdateStaffEmploymentUseCase,
)
from app.application.staff.commands.update_staff_qualifications import (
    UpdateStaffQualificationsUseCase,
)
from app.application.staff.queries.get_staff import GetStaffUseCase
from app.application.staff.queries.list_staffs import ListStaffsUseCase
from app.application.store.commands.change_insurance_pharmacy_number import (
    ChangeInsurancePharmacyNumberUseCase,
)
from app.application.store.commands.change_store_address import (
    ChangeStoreAddressUseCase,
)
from app.application.store.commands.change_store_business_hours import (
    ChangeStoreBusinessHoursUseCase,
)
from app.application.store.commands.change_store_code import ChangeStoreCodeUseCase
from app.application.store.commands.change_store_contact_info import (
    ChangeStoreContactInfoUseCase,
)
from app.application.store.commands.change_store_names import ChangeStoreNamesUseCase
from app.application.store.commands.change_store_status import ChangeStoreStatusUseCase
from app.application.store.commands.manage_safety_manager import (
    AppointSafetyManagerUseCase,
    RemoveSafetyManagerUseCase,
)
from app.application.store.commands.manage_store_manager import (
    ManageStoreManagerUseCase,
)
from app.application.store.commands.register_store import RegisterStoreUseCase
from app.application.store.commands.revoke_store_closure import (
    RevokeStoreClosureUseCase,
)
from app.application.store.commands.update_certifications import (
    UpdateCertificationsUseCase,
)
from app.application.store.commands.update_licenses import (
    UpdateStoreLicensesUseCase,
)
from app.application.store.commands.update_public_expense_designations import (
    UpdatePublicExpenseDesignationsUseCase,
)
from app.application.store.commands.update_store_policy import (
    UpdateStorePolicyUseCase,
)
from app.application.store.queries.get_effective_policy import (
    GetEffectivePolicyUseCase,
)
from app.application.store.queries.get_store import GetStoreUseCase
from app.application.store.queries.get_store_opening_status import (
    GetStoreOpeningStatusUseCase,
)
from app.application.store.queries.list_stores import ListStoresUseCase
from app.domain.corporate.services import CorporateNameUniquenessService
from app.domain.coverage.services import (
    CoverageSelectionService,
    PatientCoverageConflictService,
)
from app.domain.medicine_catalog.services import MedicineEffectivePeriodConflictService
from app.domain.shared.actor import AccountPersonId, UserAccountId
from app.domain.staff.services import (
    StaffCodeUniquenessService,
    StaffStoreAssignmentService,
)
from app.domain.store.services import (
    InsurancePharmacyNumberUniquenessService,
    StoreCodeUniquenessService,
    StoreNameUniquenessService,
)
from app.infrastructure.readers.corporate_list_corporates import (
    ListCorporatesProjection,
)
from app.infrastructure.readers.coverage_get_last_coverage_selection import (
    GetLastCoverageSelectionProjection,
)
from app.infrastructure.readers.coverage_get_patient_coverage import (
    GetPatientCoverageProjection,
)
from app.infrastructure.readers.coverage_list_patient_coverages import (
    ListPatientCoveragesProjection,
)
from app.infrastructure.readers.medicine_catalog_get_effective_medicine import (
    GetEffectiveMedicineProjection,
)
from app.infrastructure.readers.patient_get_patient import GetPatientProjection
from app.infrastructure.readers.patient_get_patient_external_identifier import (
    GetPatientExternalIdentifierProjection,
)
from app.infrastructure.readers.patient_get_patient_heading import (
    GetPatientHeadingProjection,
)
from app.infrastructure.readers.patient_list_patient_external_identifiers import (
    ListPatientExternalIdentifiersProjection,
)
from app.infrastructure.readers.staff_get_staff import GetStaffProjection
from app.infrastructure.readers.staff_list_staffs import ListStaffsProjection
from app.infrastructure.readers.store_get_effective_policy import (
    GetEffectivePolicyProjection,
)
from app.infrastructure.readers.store_get_store import GetStoreProjection
from app.infrastructure.readers.store_get_store_opening_status import (
    GetStoreOpeningStatusProjection,
)
from app.infrastructure.readers.store_list_stores import ListStoresProjection
from tests.application.staff.access_revocation_helpers import (
    create_access_revocation,
)
from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_organization_management import (
    FakeOrganizationLock,
    FakeStoreWorkBoundary,
)
from tests.fakes.in_memory_corporate_repository import InMemoryCorporateRepository
from tests.fakes.in_memory_coverage_selection_record_repository import (
    InMemoryCoverageSelectionRecordRepository,
)
from tests.fakes.in_memory_identity_repositories import (
    FakeCredentialWriter,
    InMemoryAccountPersonRepository,
    InMemoryCorporateMembershipRepository,
    InMemoryStaffPersonLinkRepository,
    InMemoryUserAccountRepository,
)
from tests.fakes.in_memory_manager_assignment_repository import (
    InMemoryStoreManagerAssignmentRepository,
)
from tests.fakes.in_memory_medication_history_repository import (
    InMemoryMedicationHistoryRepository,
)
from tests.fakes.in_memory_medicine_catalog_repository import (
    InMemoryMedicineCatalogRepository,
)
from tests.fakes.in_memory_patient_coverage_repository import (
    InMemoryPatientCoverageRepository,
)
from tests.fakes.in_memory_patient_repository import (
    InMemoryPatientExternalIdentifierRepository,
    InMemoryPatientRepository,
)
from tests.fakes.in_memory_reception_repository import InMemoryReceptionRepository
from tests.fakes.in_memory_staff_repository import InMemoryStaffRepository
from tests.fakes.in_memory_store_repository import InMemoryStoreRepository
from tests.fakes.null_unit_of_work import NullUnitOfWork

_VENDOR_PERSON_ID = AccountPersonId.generate()
_VENDOR_ACCOUNT_ID = UserAccountId.generate()


def vendor_admin() -> ActorContext:
    """全法人を操作できるベンダーシステム管理者。"""
    return ResolvedActorContext(
        principal_id="test-actor",
        roles=frozenset({ActorRole.VENDOR_SYSTEM_ADMIN}),
        person_id=_VENDOR_PERSON_ID,
        account_id=_VENDOR_ACCOUNT_ID,
    )


def _access_for(
    repository: InMemoryCorporateRepository,
    actor: ActorContext | None = None,
) -> CorporateAccessService:
    effective_actor = vendor_admin() if actor is None else actor
    return CorporateAccessService(repository, AuthorizationService(effective_actor))


def create_corporate_use_cases(
    repository: InMemoryCorporateRepository,
    *,
    actor: ActorContext | None = None,
) -> CorporateUseCases:
    """インメモリRepositoryの上に法人ユースケース束を組み立てる。"""
    uniqueness = CorporateNameUniquenessService(repository)
    access = _access_for(repository, actor=actor)
    return CorporateUseCases(
        list=ListCorporatesUseCase(
            reader=ListCorporatesProjection(repository),
            authorization=AuthorizationService(vendor_admin()),
        ),
        register=RegisterCorporateUseCase(repository, uniqueness, access),
        get=GetCorporateUseCase(access),
        change_name=ChangeCorporateNameUseCase(repository, uniqueness, access),
        change_representative=ChangeRepresentativeUseCase(repository, access),
        change_status=ChangeCorporateStatusUseCase(
            repository, access, FakeOrganizationLock()
        ),
        update_policy=UpdateCorporatePolicyUseCase(repository, access),
        update_details=UpdateCorporateDetailsUseCase(repository, access),
    )


def create_store_use_cases(
    repository: InMemoryStoreRepository,
    corporate_repository: InMemoryCorporateRepository,
    *,
    actor: ActorContext | None = None,
) -> StoreUseCases:
    """インメモリRepositoryの上に店舗ユースケース束を組み立てる。"""
    names = StoreNameUniquenessService(repository)
    codes = StoreCodeUniquenessService(repository)
    numbers = InsurancePharmacyNumberUniquenessService(repository)
    access = _access_for(corporate_repository, actor=actor)
    staff_reference = ManagerStaffAdapter(InMemoryStaffRepository())
    return StoreUseCases(
        change_status=ChangeStoreStatusUseCase(
            repository,
            InMemoryStoreManagerAssignmentRepository(),
            FakeStoreWorkBoundary(),
            access,
            FakeClock(),
            NullUnitOfWork(),
            FakeOrganizationLock(),
        ),
        revoke_closure=RevokeStoreClosureUseCase(
            repository,
            access,
            FakeClock(),
            NullUnitOfWork(),
            FakeOrganizationLock(),
        ),
        manage_manager=ManageStoreManagerUseCase(
            repository,
            staff_reference,
            InMemoryStoreManagerAssignmentRepository(),
            StaffPersonAdapter(InMemoryStaffPersonLinkRepository()),
            access,
            FakeClock(),
            NullUnitOfWork(),
            FakeOrganizationLock(),
        ),
        register=RegisterStoreUseCase(repository, names, codes, numbers, access),
        get=GetStoreUseCase(
            reader=GetStoreProjection(repository), corporate_access=access
        ),
        list_by_corporate=ListStoresUseCase(
            reader=ListStoresProjection(repository), corporate_access=access
        ),
        change_names=ChangeStoreNamesUseCase(repository, names, access),
        change_code=ChangeStoreCodeUseCase(repository, codes, access),
        change_address=ChangeStoreAddressUseCase(repository, access),
        change_contact_info=ChangeStoreContactInfoUseCase(repository, access),
        change_business_hours=ChangeStoreBusinessHoursUseCase(repository, access),
        opening_status=GetStoreOpeningStatusUseCase(
            reader=GetStoreOpeningStatusProjection(repository, FakeClock()),
            corporate_access=access,
        ),
        change_insurance_pharmacy_number=ChangeInsurancePharmacyNumberUseCase(
            repository, numbers, access
        ),
        update_licenses=UpdateStoreLicensesUseCase(repository, access),
        update_policy=UpdateStorePolicyUseCase(
            repository,
            access,
            EffectivePolicyResolver(corporate_repository, repository),
        ),
        effective_policy=GetEffectivePolicyUseCase(
            reader=GetEffectivePolicyProjection(corporate_repository, repository),
            corporate_access=access,
        ),
        update_certifications=UpdateCertificationsUseCase(repository, access),
        update_public_expense_designations=UpdatePublicExpenseDesignationsUseCase(
            repository, access
        ),
        appoint_safety_manager=AppointSafetyManagerUseCase(
            repository, staff_reference, access
        ),
        remove_safety_manager=RemoveSafetyManagerUseCase(repository, access),
    )


def create_staff_use_cases(
    staffs: InMemoryStaffRepository,
    stores: InMemoryStoreRepository,
    corporate_repository: InMemoryCorporateRepository,
    clock: Clock,
) -> StaffUseCases:
    """インメモリRepositoryの上にスタッフユースケース束を組み立てる。"""
    access = _access_for(corporate_repository)
    code_uniqueness = StaffCodeUniquenessService(staffs)
    assignment = StaffStoreAssignmentService()
    account_registration = StaffAccountRegistrationAdapter(
        people=InMemoryAccountPersonRepository(),
        accounts=InMemoryUserAccountRepository(),
        memberships=InMemoryCorporateMembershipRepository(),
        links=InMemoryStaffPersonLinkRepository(),
        credentials=FakeCredentialWriter(),
    )
    return StaffUseCases(
        register=RegisterStaffUseCase(
            staff_repository=staffs,
            store_repository=StaffStoreAdapter(stores),
            uniqueness_service=code_uniqueness,
            assignment_service=assignment,
            corporate_access=access,
            account_registration=account_registration,
            unit_of_work=NullUnitOfWork(),
            lock=FakeOrganizationLock(),
            clock=clock,
            store_managers=InMemoryStoreManagerAssignmentRepository(),
        ),
        get=GetStaffUseCase(
            reader=GetStaffProjection(staffs),
            corporate_access=access,
            clock=clock,
        ),
        list_by_corporate=ListStaffsUseCase(
            reader=ListStaffsProjection(staffs), corporate_access=access
        ),
        change_names=ChangeStaffNamesUseCase(staffs, access),
        change_job_title=ChangeStaffJobTitleUseCase(staffs, access),
        update_qualifications=UpdateStaffQualificationsUseCase(staffs, access),
        transfer_home_store=TransferStaffHomeStoreUseCase(
            staffs, StaffStoreAdapter(stores), assignment, access
        ),
        assign_concurrent_store=AssignStaffConcurrentStoreUseCase(
            staffs, StaffStoreAdapter(stores), assignment, access
        ),
        remove_concurrent_store=RemoveStaffConcurrentStoreUseCase(
            staffs, StaffStoreAdapter(stores), assignment, access
        ),
        activate=ActivateStaffUseCase(staffs, access),
        deactivate=DeactivateStaffUseCase(
            staffs, access, create_access_revocation(), clock
        ),
        update_employment=UpdateStaffEmploymentUseCase(staffs, access),
        start_leave=StartStaffLeaveUseCase(staffs, access),
        return_from_leave=ReturnStaffFromLeaveUseCase(staffs, access),
    )


def create_patient_use_cases(
    patients: InMemoryPatientRepository,
    identifiers: InMemoryPatientExternalIdentifierRepository,
    corporate_repository: InMemoryCorporateRepository,
    *,
    actor: ActorContext | None = None,
) -> PatientUseCases:
    """インメモリRepositoryの上に患者ユースケース束を組み立てる。"""
    access = (
        _access_for(corporate_repository)
        if actor is None
        else CorporateAccessService(corporate_repository, AuthorizationService(actor))
    )
    clock = FakeClock()
    return PatientUseCases(
        register=RegisterPatientUseCase(patients, access),
        get=GetPatientUseCase(
            reader=GetPatientProjection(patients), corporate_access=access
        ),
        change_names=ChangePatientNamesUseCase(patients, access, clock),
        change_birth_date=ChangePatientBirthDateUseCase(patients, access, clock),
        change_profile=ChangePatientProfileUseCase(patients, access, clock),
        get_heading=GetPatientHeadingUseCase(
            reader=GetPatientHeadingProjection(patients),
            corporate_access=access,
        ),
        change_heading=ChangePatientHeadingUseCase(patients, access, clock),
        deactivate=DeactivatePatientUseCase(patients, access, clock),
        reactivate=ReactivatePatientUseCase(patients, access, clock),
        merge=MergePatientsUseCase(patients, access, clock),
        register_external_identifier=RegisterPatientExternalIdentifierUseCase(
            patients, identifiers, access
        ),
        get_external_identifier=GetPatientExternalIdentifierUseCase(
            reader=GetPatientExternalIdentifierProjection(identifiers),
            corporate_access=access,
        ),
        list_external_identifiers=ListPatientExternalIdentifiersUseCase(
            reader=ListPatientExternalIdentifiersProjection(patients, identifiers),
            corporate_access=access,
        ),
        deactivate_external_identifier=DeactivatePatientExternalIdentifierUseCase(
            identifiers, access
        ),
    )


def create_coverage_use_cases(
    coverages: InMemoryPatientCoverageRepository,
    patients: InMemoryPatientRepository,
    stores: InMemoryStoreRepository,
    records: InMemoryCoverageSelectionRecordRepository,
    corporate_repository: InMemoryCorporateRepository,
    clock: Clock,
) -> CoverageUseCases:
    """インメモリRepositoryの上に資格台帳ユースケース束を組み立てる。"""
    access = _access_for(corporate_repository)
    patient_reference = CoveragePatientReferenceAdapter(patients)
    store_reference = CoverageStoreReferenceAdapter(stores)
    selection = CoverageSelectionBuilder(coverages, CoverageSelectionService())
    conflict = PatientCoverageConflictService()
    return CoverageUseCases(
        register=RegisterPatientCoverageUseCase(
            coverages, patient_reference, conflict, access
        ),
        get=GetPatientCoverageUseCase(
            reader=GetPatientCoverageProjection(coverages),
            corporate_access=access,
        ),
        list_by_patient=ListPatientCoveragesUseCase(
            reader=ListPatientCoveragesProjection(coverages),
            patient_reference=patient_reference,
            corporate_access=access,
        ),
        change_period=ChangePatientCoveragePeriodUseCase(coverages, conflict, access),
        deactivate=DeactivatePatientCoverageUseCase(coverages, access),
        record_coverage_selection=RecordCoverageSelectionUseCase(
            records,
            access,
            store_reference,
            patient_reference,
            selection,
            clock,
        ),
        get_last_coverage_selection=GetLastCoverageSelectionUseCase(
            reader=GetLastCoverageSelectionProjection(records, selection),
            corporate_access=access,
            store_reference=store_reference,
            patient_reference=patient_reference,
        ),
    )


def create_reception_use_cases(
    receptions: InMemoryReceptionRepository,
    medication_histories: InMemoryMedicationHistoryRepository,
    corporate_repository: InMemoryCorporateRepository,
) -> ReceptionUseCases:
    """インメモリRepositoryの上に受付固有のユースケース束を組み立てる。"""
    access = _access_for(corporate_repository)
    return ReceptionUseCases(
        associate_medication_history=AssociateReceptionMedicationHistoryUseCase(
            reception_repository=receptions,
            medication_history_reference=ReceptionMedicationHistoryAssociationAdapter(
                medication_histories
            ),
            corporate_access=access,
            unit_of_work=NullUnitOfWork(),
        ),
    )


def create_medicine_catalog_use_cases(
    medicines: InMemoryMedicineCatalogRepository,
    authorization: AuthorizationService | None = None,
) -> MedicineCatalogUseCases:
    """インメモリRepositoryの上に医薬品マスタユースケース束を組み立てる。

    薬価基準は法人ごとに内容が違わないので、対象法人を伴わない
    ``AuthorizationService`` を直接渡す。
    """
    auth = authorization or AuthorizationService(vendor_admin())
    return MedicineCatalogUseCases(
        register=RegisterMedicineUseCase(
            medicines, auth, MedicineEffectivePeriodConflictService()
        ),
        get_effective=GetEffectiveMedicineUseCase(
            reader=GetEffectiveMedicineProjection(medicines), authorization=auth
        ),
        import_yj=ImportYjCatalogUseCase(medicines, auth),
    )
