"""プレゼンテーション層テスト用のユースケース束。

HTTPの結線だけを確かめたいので、PostgreSQLのスコープは通さず、インメモリ
Repositoryで組んだ本物のユースケースを束へ入れて差し替える。認可の判定そのものは
Application層のテストが確かめているため、ここでは固定の主体を使う。
"""

from __future__ import annotations

from app.application.access_control.models import (
    ActorContext,
    ActorRole,
    ResolvedActorContext,
)
from app.application.access_control.policy import AuthorizationService
from app.application.common.clock import Clock
from app.application.composition.coverage_references import (
    CoveragePatientReferenceAdapter,
)
from app.application.composition.coverage_selection_adapter import (
    CoverageSelectionAdapter,
)
from app.application.composition.reception_references import (
    ReceptionPatientReferenceAdapter,
    ReceptionStoreReferenceAdapter,
)
from app.application.composition.staff_person_adapter import StaffPersonAdapter
from app.application.corporate.change_corporate_name import ChangeCorporateNameUseCase
from app.application.corporate.change_corporate_status import (
    ChangeCorporateStatusUseCase,
)
from app.application.corporate.change_representative import ChangeRepresentativeUseCase
from app.application.corporate.corporate_access import CorporateAccessService
from app.application.corporate.get_corporate import GetCorporateUseCase
from app.application.corporate.list_corporates import ListCorporatesUseCase
from app.application.corporate.register_corporate import RegisterCorporateUseCase
from app.application.coverage.change_patient_coverage_period import (
    ChangePatientCoveragePeriodUseCase,
)
from app.application.coverage.deactivate_patient_coverage import (
    DeactivatePatientCoverageUseCase,
)
from app.application.coverage.get_patient_coverage import GetPatientCoverageUseCase
from app.application.coverage.list_patient_coverages import ListPatientCoveragesUseCase
from app.application.coverage.register_patient_coverage import (
    RegisterPatientCoverageUseCase,
)
from app.application.medicine_catalog.get_medicine import GetEffectiveMedicineUseCase
from app.application.medicine_catalog.import_yj_catalog import ImportYjCatalogUseCase
from app.application.medicine_catalog.register_medicine import RegisterMedicineUseCase
from app.application.patient.change_patient_birth_date import (
    ChangePatientBirthDateUseCase,
)
from app.application.patient.change_patient_names import ChangePatientNamesUseCase
from app.application.patient.deactivate_patient import DeactivatePatientUseCase
from app.application.patient.deactivate_patient_external_identifier import (
    DeactivatePatientExternalIdentifierUseCase,
)
from app.application.patient.get_patient import GetPatientUseCase
from app.application.patient.get_patient_external_identifier import (
    GetPatientExternalIdentifierUseCase,
)
from app.application.patient.list_patient_external_identifiers import (
    ListPatientExternalIdentifiersUseCase,
)
from app.application.patient.merge_patients import MergePatientsUseCase
from app.application.patient.reactivate_patient import ReactivatePatientUseCase
from app.application.patient.register_patient import RegisterPatientUseCase
from app.application.patient.register_patient_external_identifier import (
    RegisterPatientExternalIdentifierUseCase,
)
from app.application.reception.get_last_coverage_selection import (
    GetLastCoverageSelectionUseCase,
)
from app.application.reception.record_coverage_selection import (
    RecordCoverageSelectionUseCase,
)
from app.application.staff.activate_staff import ActivateStaffUseCase
from app.application.staff.assign_concurrent_store import (
    AssignStaffConcurrentStoreUseCase,
)
from app.application.staff.change_staff_job_title import ChangeStaffJobTitleUseCase
from app.application.staff.change_staff_names import ChangeStaffNamesUseCase
from app.application.staff.deactivate_staff import DeactivateStaffUseCase
from app.application.staff.get_staff import GetStaffUseCase
from app.application.staff.list_staffs import ListStaffsUseCase
from app.application.staff.register_staff import RegisterStaffUseCase
from app.application.staff.remove_concurrent_store import (
    RemoveStaffConcurrentStoreUseCase,
)
from app.application.staff.transfer_home_store import TransferStaffHomeStoreUseCase
from app.application.staff.update_qualifications import UpdateStaffQualificationsUseCase
from app.application.store.business_hours import (
    ChangeStoreBusinessHoursUseCase,
    GetStoreOpeningStatusUseCase,
)
from app.application.store.change_insurance_pharmacy_number import (
    ChangeInsurancePharmacyNumberUseCase,
)
from app.application.store.change_store_address import ChangeStoreAddressUseCase
from app.application.store.change_store_code import ChangeStoreCodeUseCase
from app.application.store.change_store_contact_info import (
    ChangeStoreContactInfoUseCase,
)
from app.application.store.change_store_name import ChangeStoreNamesUseCase
from app.application.store.get_store import GetStoreUseCase
from app.application.store.list_stores import ListStoresUseCase
from app.application.store.management import (
    ChangeStoreStatusUseCase,
    ManageStoreManagerUseCase,
    RevokeStoreClosureUseCase,
)
from app.application.store.register_store import RegisterStoreUseCase
from app.domain.corporate.services import CorporateNameUniquenessService
from app.domain.coverage.combination import CoverageSelectionService
from app.domain.coverage.services import PatientCoverageConflictService
from app.domain.identity.primitives import AccountPersonId, UserAccountId
from app.domain.medicine_catalog.services import MedicineEffectivePeriodConflictService
from app.domain.staff.services import (
    StaffCodeUniquenessService,
    StaffStoreAssignmentService,
)
from app.domain.store.services import (
    InsurancePharmacyNumberUniquenessService,
    StoreCodeUniquenessService,
    StoreNameUniquenessService,
)
from app.infrastructure.di.bundles.medicine_catalog import MedicineCatalogUseCases
from app.infrastructure.di.bundles.organization import (
    CorporateUseCases,
    StaffUseCases,
    StoreUseCases,
)
from app.infrastructure.di.bundles.patient_care import (
    CoverageUseCases,
    PatientUseCases,
    ReceptionUseCases,
)
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
    InMemoryStaffPersonLinkRepository,
)
from tests.fakes.in_memory_manager_assignment_repository import (
    InMemoryStoreManagerAssignmentRepository,
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


def _access_for(repository: InMemoryCorporateRepository) -> CorporateAccessService:
    return CorporateAccessService(repository, AuthorizationService(vendor_admin()))


def create_corporate_use_cases(
    repository: InMemoryCorporateRepository,
) -> CorporateUseCases:
    """インメモリRepositoryの上に法人ユースケース束を組み立てる。"""
    uniqueness = CorporateNameUniquenessService(repository)
    access = _access_for(repository)
    return CorporateUseCases(
        list=ListCorporatesUseCase(repository, AuthorizationService(vendor_admin())),
        register=RegisterCorporateUseCase(repository, uniqueness, access),
        get=GetCorporateUseCase(access),
        change_name=ChangeCorporateNameUseCase(repository, uniqueness, access),
        change_representative=ChangeRepresentativeUseCase(repository, access),
        change_status=ChangeCorporateStatusUseCase(repository, access),
    )


def create_store_use_cases(
    repository: InMemoryStoreRepository,
    corporate_repository: InMemoryCorporateRepository,
) -> StoreUseCases:
    """インメモリRepositoryの上に店舗ユースケース束を組み立てる。"""
    names = StoreNameUniquenessService(repository)
    codes = StoreCodeUniquenessService(repository)
    numbers = InsurancePharmacyNumberUniquenessService(repository)
    access = _access_for(corporate_repository)
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
            InMemoryStaffRepository(),
            InMemoryStoreManagerAssignmentRepository(),
            StaffPersonAdapter(InMemoryStaffPersonLinkRepository()),
            access,
            FakeClock(),
            NullUnitOfWork(),
            FakeOrganizationLock(),
        ),
        register=RegisterStoreUseCase(repository, names, codes, numbers, access),
        get=GetStoreUseCase(repository, access),
        list_by_corporate=ListStoresUseCase(repository, access),
        change_names=ChangeStoreNamesUseCase(repository, names, access),
        change_code=ChangeStoreCodeUseCase(repository, codes, access),
        change_address=ChangeStoreAddressUseCase(repository, access),
        change_contact_info=ChangeStoreContactInfoUseCase(repository, access),
        change_business_hours=ChangeStoreBusinessHoursUseCase(repository, access),
        opening_status=GetStoreOpeningStatusUseCase(repository, access, FakeClock()),
        change_insurance_pharmacy_number=ChangeInsurancePharmacyNumberUseCase(
            repository, numbers, access
        ),
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
    return StaffUseCases(
        register=RegisterStaffUseCase(
            staffs, stores, code_uniqueness, assignment, access
        ),
        get=GetStaffUseCase(staffs, access, clock),
        list_by_corporate=ListStaffsUseCase(staffs, access),
        change_names=ChangeStaffNamesUseCase(staffs, access),
        change_job_title=ChangeStaffJobTitleUseCase(staffs, access),
        update_qualifications=UpdateStaffQualificationsUseCase(staffs, access),
        transfer_home_store=TransferStaffHomeStoreUseCase(
            staffs, stores, assignment, access
        ),
        assign_concurrent_store=AssignStaffConcurrentStoreUseCase(
            staffs, stores, assignment, access
        ),
        remove_concurrent_store=RemoveStaffConcurrentStoreUseCase(
            staffs, stores, assignment, access
        ),
        activate=ActivateStaffUseCase(staffs, access),
        deactivate=DeactivateStaffUseCase(staffs, access, create_access_revocation()),
    )


def create_patient_use_cases(
    patients: InMemoryPatientRepository,
    identifiers: InMemoryPatientExternalIdentifierRepository,
    corporate_repository: InMemoryCorporateRepository,
) -> PatientUseCases:
    """インメモリRepositoryの上に患者ユースケース束を組み立てる。"""
    access = _access_for(corporate_repository)
    clock = FakeClock()
    return PatientUseCases(
        register=RegisterPatientUseCase(patients, access),
        get=GetPatientUseCase(patients, access),
        change_names=ChangePatientNamesUseCase(patients, access),
        change_birth_date=ChangePatientBirthDateUseCase(patients, access),
        deactivate=DeactivatePatientUseCase(patients, access, clock),
        reactivate=ReactivatePatientUseCase(patients, access, clock),
        merge=MergePatientsUseCase(patients, access, clock),
        register_external_identifier=RegisterPatientExternalIdentifierUseCase(
            patients, identifiers, access
        ),
        get_external_identifier=GetPatientExternalIdentifierUseCase(
            identifiers, access
        ),
        list_external_identifiers=ListPatientExternalIdentifiersUseCase(
            patients, identifiers, access
        ),
        deactivate_external_identifier=DeactivatePatientExternalIdentifierUseCase(
            identifiers, access
        ),
    )


def create_coverage_use_cases(
    coverages: InMemoryPatientCoverageRepository,
    patients: InMemoryPatientRepository,
    corporate_repository: InMemoryCorporateRepository,
) -> CoverageUseCases:
    """インメモリRepositoryの上に資格台帳ユースケース束を組み立てる。"""
    access = _access_for(corporate_repository)
    patient_reference = CoveragePatientReferenceAdapter(patients)
    conflict = PatientCoverageConflictService()
    return CoverageUseCases(
        register=RegisterPatientCoverageUseCase(
            coverages, patient_reference, conflict, access
        ),
        get=GetPatientCoverageUseCase(coverages, access),
        list_by_patient=ListPatientCoveragesUseCase(
            coverages, patient_reference, access
        ),
        change_period=ChangePatientCoveragePeriodUseCase(coverages, conflict, access),
        deactivate=DeactivatePatientCoverageUseCase(coverages, access),
    )


def create_reception_use_cases(
    records: InMemoryCoverageSelectionRecordRepository,
    stores: InMemoryStoreRepository,
    patients: InMemoryPatientRepository,
    coverages: InMemoryPatientCoverageRepository,
    corporate_repository: InMemoryCorporateRepository,
    clock: Clock,
) -> ReceptionUseCases:
    """インメモリRepositoryの上に受付ユースケース束を組み立てる。

    本番と同じく、資格の構築と再検証を同一のアダプタが担う。別実装に分けると、
    記録したときの規則と検証するときの規則が食い違いうる。
    """
    access = _access_for(corporate_repository)
    store_reference = ReceptionStoreReferenceAdapter(stores)
    patient_reference = ReceptionPatientReferenceAdapter(patients)
    selection = CoverageSelectionAdapter(coverages, CoverageSelectionService())
    return ReceptionUseCases(
        record_coverage_selection=RecordCoverageSelectionUseCase(
            records, access, store_reference, patient_reference, selection, clock
        ),
        get_last_coverage_selection=GetLastCoverageSelectionUseCase(
            records, access, store_reference, patient_reference, selection
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
        get_effective=GetEffectiveMedicineUseCase(medicines, auth),
        import_yj=ImportYjCatalogUseCase(medicines, auth),
    )
