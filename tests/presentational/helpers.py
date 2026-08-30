"""プレゼンテーション層テスト用のユースケース束。

HTTPの結線だけを確かめたいので、PostgreSQLのスコープは通さず、インメモリ
Repositoryで組んだ本物のユースケースを束へ入れて差し替える。認可の判定そのものは
Application層のテストが確かめているため、ここでは固定の主体を使う。
"""

from __future__ import annotations

from app.application.access_control import ActorContext, AuthorizationService
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
from app.application.corporate import (
    ChangeCorporateNameUseCase,
    ChangeCorporateStatusUseCase,
    ChangeRepresentativeUseCase,
    CorporateAccessService,
    GetCorporateUseCase,
    RegisterCorporateUseCase,
)
from app.application.coverage import (
    ChangePatientCoveragePeriodUseCase,
    DeactivatePatientCoverageUseCase,
    GetPatientCoverageUseCase,
    ListPatientCoveragesUseCase,
    RegisterPatientCoverageUseCase,
)
from app.application.medicine_catalog import (
    GetEffectiveMedicineUseCase,
    RegisterMedicineUseCase,
)
from app.application.patient import (
    ChangePatientBirthDateUseCase,
    ChangePatientNamesUseCase,
    DeactivatePatientExternalIdentifierUseCase,
    GetPatientExternalIdentifierUseCase,
    GetPatientUseCase,
    ListPatientExternalIdentifiersUseCase,
    RegisterPatientExternalIdentifierUseCase,
    RegisterPatientUseCase,
)
from app.application.reception import (
    GetLastCoverageSelectionUseCase,
    RecordCoverageSelectionUseCase,
)
from app.application.staff import (
    ActivateStaffUseCase,
    AssignStaffConcurrentStoreUseCase,
    ChangeStaffJobTitleUseCase,
    ChangeStaffNamesUseCase,
    DeactivateStaffUseCase,
    GetStaffUseCase,
    ListStaffsUseCase,
    RegisterStaffUseCase,
    RemoveStaffConcurrentStoreUseCase,
    TransferStaffHomeStoreUseCase,
    UpdateStaffQualificationsUseCase,
)
from app.application.store import (
    ChangeInsurancePharmacyNumberUseCase,
    ChangeStoreAddressUseCase,
    ChangeStoreCodeUseCase,
    ChangeStoreContactInfoUseCase,
    ChangeStoreNamesUseCase,
    GetStoreUseCase,
    ListStoresUseCase,
    RegisterStoreUseCase,
)
from app.domain.corporate import CorporateNameUniquenessService
from app.domain.coverage.combination import CoverageSelectionService
from app.domain.coverage.services import PatientCoverageConflictService
from app.domain.medicine_catalog.services import MedicineEffectivePeriodConflictService
from app.domain.staff.services import (
    StaffCodeUniquenessService,
    StaffStoreAssignmentService,
)
from app.domain.store import (
    InsurancePharmacyNumberUniquenessService,
    StoreCodeUniquenessService,
    StoreNameUniquenessService,
)
from app.infrastructure.composition import (
    CorporateUseCases,
    CoverageUseCases,
    MedicineCatalogUseCases,
    PatientUseCases,
    ReceptionUseCases,
    StaffUseCases,
    StoreUseCases,
)
from tests.fakes.in_memory_corporate_repository import InMemoryCorporateRepository
from tests.fakes.in_memory_coverage_selection_record_repository import (
    InMemoryCoverageSelectionRecordRepository,
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


def vendor_admin() -> ActorContext:
    """全法人を操作できるベンダーシステム管理者。"""
    return ActorContext.vendor_system_admin(principal_id="test-actor")


def _access_for(repository: InMemoryCorporateRepository) -> CorporateAccessService:
    return CorporateAccessService(repository, AuthorizationService(vendor_admin()))


def create_corporate_use_cases(
    repository: InMemoryCorporateRepository,
) -> CorporateUseCases:
    """インメモリRepositoryの上に法人ユースケース束を組み立てる。"""
    uniqueness = CorporateNameUniquenessService(repository)
    access = _access_for(repository)
    return CorporateUseCases(
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
        register=RegisterStoreUseCase(repository, names, codes, numbers, access),
        get=GetStoreUseCase(repository, access),
        list_by_corporate=ListStoresUseCase(repository, access),
        change_names=ChangeStoreNamesUseCase(repository, names, access),
        change_code=ChangeStoreCodeUseCase(repository, codes, access),
        change_address=ChangeStoreAddressUseCase(repository, access),
        change_contact_info=ChangeStoreContactInfoUseCase(repository, access),
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
        deactivate=DeactivateStaffUseCase(staffs, access),
    )


def create_patient_use_cases(
    patients: InMemoryPatientRepository,
    identifiers: InMemoryPatientExternalIdentifierRepository,
    corporate_repository: InMemoryCorporateRepository,
) -> PatientUseCases:
    """インメモリRepositoryの上に患者ユースケース束を組み立てる。"""
    access = _access_for(corporate_repository)
    return PatientUseCases(
        register=RegisterPatientUseCase(patients, access),
        get=GetPatientUseCase(patients, access),
        change_names=ChangePatientNamesUseCase(patients, access),
        change_birth_date=ChangePatientBirthDateUseCase(patients, access),
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
) -> MedicineCatalogUseCases:
    """インメモリRepositoryの上に医薬品マスタユースケース束を組み立てる。

    薬価基準は法人ごとに内容が違わないので、対象法人を伴わない
    ``AuthorizationService`` を直接渡す。
    """
    authorization = AuthorizationService(vendor_admin())
    return MedicineCatalogUseCases(
        register=RegisterMedicineUseCase(
            medicines, authorization, MedicineEffectivePeriodConflictService()
        ),
        get_effective=GetEffectiveMedicineUseCase(medicines, authorization),
    )
