"""法人・店舗・スタッフのユースケース束。

この3つは所属関係で繋がる（スタッフは店舗に、店舗は法人に属する）。
いずれも ``CorporateAccessService`` で対象法人の認可と有効状態を確かめる。"""

from __future__ import annotations

from app.application.access_control.policy import AuthorizationService
from app.application.common.clock import Clock
from app.application.composition.organization_snapshot_mapping import (
    ManagerStaffAdapter,
    StaffStoreAdapter,
)
from app.application.composition.staff_integrity import (
    StaffAccessRevocationService,
)
from app.application.composition.staff_person_adapter import StaffPersonAdapter
from app.application.composition.use_case_bundles import (
    CorporateUseCases,
    StaffUseCases,
    StoreUseCases,
)
from app.application.corporate.change_corporate_name import ChangeCorporateNameUseCase
from app.application.corporate.change_corporate_status import (
    ChangeCorporateStatusUseCase,
)
from app.application.corporate.change_representative import ChangeRepresentativeUseCase
from app.application.corporate.corporate_access import CorporateAccessService
from app.application.corporate.get_corporate import GetCorporateUseCase
from app.application.corporate.list_corporates import ListCorporatesUseCase
from app.application.corporate.register_corporate import RegisterCorporateUseCase
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
from app.domain.staff.services import (
    StaffCodeUniquenessService,
    StaffStoreAssignmentService,
)
from app.domain.store.services import (
    InsurancePharmacyNumberUniquenessService,
    StoreCodeUniquenessService,
    StoreNameUniquenessService,
)
from app.infrastructure.di.repositories import (
    PostgresRepositorySet,
)
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.infrastructure.postgres.organization_lock import PostgresOrganizationLock
from app.infrastructure.store.postgres.work_boundary import PostgresStoreWorkBoundary

# --------------------------------------------------------------------------
# 法人
# --------------------------------------------------------------------------


def build_corporate_use_cases(
    repositories: PostgresRepositorySet,
    corporate_access: CorporateAccessService,
    unit_of_work: PostgresUnitOfWork,
) -> CorporateUseCases:
    """法人ユースケースを組み立てる。"""
    repository = repositories.corporate
    uniqueness = CorporateNameUniquenessService(repository)
    return CorporateUseCases(
        list=ListCorporatesUseCase(
            repository, AuthorizationService(corporate_access.actor)
        ),
        register=RegisterCorporateUseCase(repository, uniqueness, corporate_access),
        get=GetCorporateUseCase(corporate_access),
        change_name=ChangeCorporateNameUseCase(
            repository, uniqueness, corporate_access
        ),
        change_representative=ChangeRepresentativeUseCase(repository, corporate_access),
        change_status=ChangeCorporateStatusUseCase(
            repository, corporate_access, PostgresOrganizationLock(unit_of_work)
        ),
    )


# --------------------------------------------------------------------------
# 店舗
# --------------------------------------------------------------------------


def build_store_use_cases(
    repositories: PostgresRepositorySet,
    corporate_access: CorporateAccessService,
    clock: Clock,
    unit_of_work: PostgresUnitOfWork,
) -> StoreUseCases:
    """店舗ユースケースを組み立てる。"""
    repository = repositories.store
    name_uniqueness = StoreNameUniquenessService(repository)
    code_uniqueness = StoreCodeUniquenessService(repository)
    number_uniqueness = InsurancePharmacyNumberUniquenessService(repository)
    return StoreUseCases(
        change_status=ChangeStoreStatusUseCase(
            repository,
            repositories.manager_assignment,
            PostgresStoreWorkBoundary(unit_of_work),
            corporate_access,
            clock,
            unit_of_work,
            PostgresOrganizationLock(unit_of_work),
        ),
        revoke_closure=RevokeStoreClosureUseCase(
            repository,
            corporate_access,
            clock,
            unit_of_work,
            PostgresOrganizationLock(unit_of_work),
        ),
        manage_manager=ManageStoreManagerUseCase(
            repository,
            ManagerStaffAdapter(repositories.staff),
            repositories.manager_assignment,
            StaffPersonAdapter(repositories.staff_person_link),
            corporate_access,
            clock,
            unit_of_work,
            PostgresOrganizationLock(unit_of_work),
        ),
        register=RegisterStoreUseCase(
            repository,
            name_uniqueness,
            code_uniqueness,
            number_uniqueness,
            corporate_access,
        ),
        get=GetStoreUseCase(repository, corporate_access),
        list_by_corporate=ListStoresUseCase(repository, corporate_access),
        change_names=ChangeStoreNamesUseCase(
            repository, name_uniqueness, corporate_access
        ),
        change_code=ChangeStoreCodeUseCase(
            repository, code_uniqueness, corporate_access
        ),
        change_address=ChangeStoreAddressUseCase(repository, corporate_access),
        change_contact_info=ChangeStoreContactInfoUseCase(repository, corporate_access),
        change_insurance_pharmacy_number=ChangeInsurancePharmacyNumberUseCase(
            repository, number_uniqueness, corporate_access
        ),
        change_business_hours=ChangeStoreBusinessHoursUseCase(
            repository, corporate_access
        ),
        opening_status=GetStoreOpeningStatusUseCase(
            repository, corporate_access, clock
        ),
    )


# --------------------------------------------------------------------------
# スタッフ
# --------------------------------------------------------------------------


def build_staff_use_cases(
    repositories: PostgresRepositorySet,
    corporate_access: CorporateAccessService,
    clock: Clock,
    unit_of_work: PostgresUnitOfWork,
) -> StaffUseCases:
    """スタッフユースケースを組み立てる。"""
    # 任命の再検証は保存前の境界（StaffAssignmentWriteGuard）が全経路へ掛ける
    # ので、ここでRepositoryを包まない。包むと ``get()`` まで管理操作のロックを
    # 取り、参照が全書き込みと直列化する。
    staff_repository = repositories.staff
    store_repository = repositories.store
    access_revocation = StaffAccessRevocationService(
        repositories.membership,
        repositories.user_account,
        PostgresOrganizationLock(unit_of_work),
    )
    code_uniqueness = StaffCodeUniquenessService(staff_repository)
    assignment = StaffStoreAssignmentService()
    return StaffUseCases(
        register=RegisterStaffUseCase(
            staff_repository,
            StaffStoreAdapter(store_repository),
            code_uniqueness,
            assignment,
            corporate_access,
        ),
        get=GetStaffUseCase(staff_repository, corporate_access, clock),
        list_by_corporate=ListStaffsUseCase(repositories.staff, corporate_access),
        change_names=ChangeStaffNamesUseCase(staff_repository, corporate_access),
        change_job_title=ChangeStaffJobTitleUseCase(staff_repository, corporate_access),
        update_qualifications=UpdateStaffQualificationsUseCase(
            staff_repository, corporate_access
        ),
        transfer_home_store=TransferStaffHomeStoreUseCase(
            staff_repository,
            StaffStoreAdapter(store_repository),
            assignment,
            corporate_access,
        ),
        assign_concurrent_store=AssignStaffConcurrentStoreUseCase(
            staff_repository,
            StaffStoreAdapter(store_repository),
            assignment,
            corporate_access,
        ),
        remove_concurrent_store=RemoveStaffConcurrentStoreUseCase(
            staff_repository,
            StaffStoreAdapter(store_repository),
            assignment,
            corporate_access,
        ),
        activate=ActivateStaffUseCase(staff_repository, corporate_access),
        deactivate=DeactivateStaffUseCase(
            staff_repository, corporate_access, access_revocation
        ),
    )


__all__ = [
    "CorporateUseCases",
    "StaffUseCases",
    "StoreUseCases",
    "build_corporate_use_cases",
    "build_staff_use_cases",
    "build_store_use_cases",
]
