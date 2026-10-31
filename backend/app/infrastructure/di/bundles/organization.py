"""法人・店舗・スタッフのユースケース束。

この3つは所属関係で繋がる（スタッフは店舗に、店舗は法人に属する）。
いずれも ``CorporateAccessService`` で対象法人の認可と有効状態を確かめる。"""

from __future__ import annotations

from app.application.access_control.policies import AuthorizationService
from app.application.common.clock import Clock
from app.application.composition.adapters.effective_policy_resolver import (
    EffectivePolicyResolver,
)
from app.application.composition.adapters.organization_snapshot_mapping import (
    ManagerStaffAdapter,
    StaffStoreAdapter,
)
from app.application.composition.adapters.staff_account_registration import (
    StaffAccountRegistrationAdapter,
)
from app.application.composition.adapters.staff_integrity import (
    StaffAccessRevocationService,
)
from app.application.composition.adapters.staff_person_adapter import StaffPersonAdapter
from app.application.composition.registry import (
    CorporateUseCases,
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
from app.application.corporate.commands.update_corporate_policy import (
    UpdateCorporatePolicyUseCase,
)
from app.application.corporate.queries.get_corporate import GetCorporateUseCase
from app.application.corporate.queries.list_corporates import ListCorporatesUseCase
from app.application.staff.commands.activate_staff import ActivateStaffUseCase
from app.application.staff.commands.assign_staff_concurrent_store import (
    AssignStaffConcurrentStoreUseCase,
)
from app.application.staff.commands.change_staff_job_title import (
    ChangeStaffJobTitleUseCase,
)
from app.application.staff.commands.change_staff_names import ChangeStaffNamesUseCase
from app.application.staff.commands.deactivate_staff import DeactivateStaffUseCase
from app.application.staff.commands.register_staff import RegisterStaffUseCase
from app.application.staff.commands.remove_staff_concurrent_store import (
    RemoveStaffConcurrentStoreUseCase,
)
from app.application.staff.commands.transfer_staff_home_store import (
    TransferStaffHomeStoreUseCase,
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
from app.application.store.commands.manage_store_manager import (
    ManageStoreManagerUseCase,
)
from app.application.store.commands.register_store import RegisterStoreUseCase
from app.application.store.commands.revoke_store_closure import (
    RevokeStoreClosureUseCase,
)
from app.application.store.commands.update_licenses import (
    UpdateStoreLicensesUseCase,
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
from app.infrastructure.identity.postgres.local_authentication import (
    PostgresCredentialWriter,
)
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.infrastructure.postgres.organization_lock import PostgresOrganizationLock
from app.infrastructure.readers.corporate_list_corporates import (
    ListCorporatesProjection,
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
            reader=ListCorporatesProjection(repository),
            authorization=AuthorizationService(corporate_access.actor),
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
        update_policy=UpdateCorporatePolicyUseCase(repository, corporate_access),
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
        get=GetStoreUseCase(
            reader=GetStoreProjection(repository),
            corporate_access=corporate_access,
        ),
        list_by_corporate=ListStoresUseCase(
            reader=ListStoresProjection(repository),
            corporate_access=corporate_access,
        ),
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
            reader=GetStoreOpeningStatusProjection(repository, clock),
            corporate_access=corporate_access,
        ),
        update_licenses=UpdateStoreLicensesUseCase(repository, corporate_access),
        update_policy=UpdateStorePolicyUseCase(
            repository,
            corporate_access,
            EffectivePolicyResolver(repositories.corporate, repository),
        ),
        effective_policy=GetEffectivePolicyUseCase(
            reader=GetEffectivePolicyProjection(repositories.corporate, repository),
            corporate_access=corporate_access,
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
    account_registration = StaffAccountRegistrationAdapter(
        people=repositories.account_person,
        accounts=repositories.user_account,
        memberships=repositories.membership,
        links=repositories.staff_person_link,
        credentials=PostgresCredentialWriter(unit_of_work),
    )
    lock = PostgresOrganizationLock(unit_of_work)
    return StaffUseCases(
        register=RegisterStaffUseCase(
            staff_repository,
            StaffStoreAdapter(store_repository),
            code_uniqueness,
            assignment,
            corporate_access,
            account_registration=account_registration,
            unit_of_work=unit_of_work,
            lock=lock,
            clock=clock,
            store_managers=repositories.manager_assignment,
        ),
        get=GetStaffUseCase(
            reader=GetStaffProjection(staff_repository),
            corporate_access=corporate_access,
            clock=clock,
        ),
        list_by_corporate=ListStaffsUseCase(
            reader=ListStaffsProjection(repositories.staff),
            corporate_access=corporate_access,
        ),
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
            staff_repository, corporate_access, access_revocation, clock
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
