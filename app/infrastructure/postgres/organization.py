"""法人・店舗・スタッフのユースケース束。

この3つは所属関係で繋がる（スタッフは店舗に、店舗は法人に属する）。
いずれも ``CorporateAccessService`` で対象法人の認可と有効状態を確かめる。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.common.clock import Clock
from app.application.corporate.change_corporate_name import ChangeCorporateNameUseCase
from app.application.corporate.change_corporate_status import (
    ChangeCorporateStatusUseCase,
)
from app.application.corporate.change_representative import ChangeRepresentativeUseCase
from app.application.corporate.corporate_access import CorporateAccessService
from app.application.corporate.get_corporate import GetCorporateUseCase
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
from app.infrastructure.postgres.repositories import PostgresRepositorySet

# --------------------------------------------------------------------------
# 法人
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CorporateUseCases:
    """法人コンテキストのユースケース。"""

    register: RegisterCorporateUseCase
    get: GetCorporateUseCase
    change_name: ChangeCorporateNameUseCase
    change_representative: ChangeRepresentativeUseCase
    change_status: ChangeCorporateStatusUseCase


def build_corporate_use_cases(
    repositories: PostgresRepositorySet,
    corporate_access: CorporateAccessService,
) -> CorporateUseCases:
    """法人ユースケースを組み立てる。"""
    repository = repositories.corporate
    uniqueness = CorporateNameUniquenessService(repository)
    return CorporateUseCases(
        register=RegisterCorporateUseCase(repository, uniqueness, corporate_access),
        get=GetCorporateUseCase(corporate_access),
        change_name=ChangeCorporateNameUseCase(
            repository, uniqueness, corporate_access
        ),
        change_representative=ChangeRepresentativeUseCase(repository, corporate_access),
        change_status=ChangeCorporateStatusUseCase(repository, corporate_access),
    )


# --------------------------------------------------------------------------
# 店舗
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class StoreUseCases:
    """店舗コンテキストのユースケース。"""

    register: RegisterStoreUseCase
    get: GetStoreUseCase
    list_by_corporate: ListStoresUseCase
    change_names: ChangeStoreNamesUseCase
    change_code: ChangeStoreCodeUseCase
    change_address: ChangeStoreAddressUseCase
    change_contact_info: ChangeStoreContactInfoUseCase
    change_insurance_pharmacy_number: ChangeInsurancePharmacyNumberUseCase


def build_store_use_cases(
    repositories: PostgresRepositorySet,
    corporate_access: CorporateAccessService,
) -> StoreUseCases:
    """店舗ユースケースを組み立てる。"""
    repository = repositories.store
    name_uniqueness = StoreNameUniquenessService(repository)
    code_uniqueness = StoreCodeUniquenessService(repository)
    number_uniqueness = InsurancePharmacyNumberUniquenessService(repository)
    return StoreUseCases(
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
    )


# --------------------------------------------------------------------------
# スタッフ
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class StaffUseCases:
    """スタッフコンテキストのユースケース。"""

    register: RegisterStaffUseCase
    get: GetStaffUseCase
    list_by_corporate: ListStaffsUseCase
    change_names: ChangeStaffNamesUseCase
    change_job_title: ChangeStaffJobTitleUseCase
    update_qualifications: UpdateStaffQualificationsUseCase
    transfer_home_store: TransferStaffHomeStoreUseCase
    assign_concurrent_store: AssignStaffConcurrentStoreUseCase
    remove_concurrent_store: RemoveStaffConcurrentStoreUseCase
    activate: ActivateStaffUseCase
    deactivate: DeactivateStaffUseCase


def build_staff_use_cases(
    repositories: PostgresRepositorySet,
    corporate_access: CorporateAccessService,
    clock: Clock,
) -> StaffUseCases:
    """スタッフユースケースを組み立てる。"""
    staff_repository = repositories.staff
    store_repository = repositories.store
    code_uniqueness = StaffCodeUniquenessService(staff_repository)
    assignment = StaffStoreAssignmentService()
    return StaffUseCases(
        register=RegisterStaffUseCase(
            staff_repository,
            store_repository,
            code_uniqueness,
            assignment,
            corporate_access,
        ),
        get=GetStaffUseCase(staff_repository, corporate_access, clock),
        list_by_corporate=ListStaffsUseCase(staff_repository, corporate_access),
        change_names=ChangeStaffNamesUseCase(staff_repository, corporate_access),
        change_job_title=ChangeStaffJobTitleUseCase(staff_repository, corporate_access),
        update_qualifications=UpdateStaffQualificationsUseCase(
            staff_repository, corporate_access
        ),
        transfer_home_store=TransferStaffHomeStoreUseCase(
            staff_repository, store_repository, assignment, corporate_access
        ),
        assign_concurrent_store=AssignStaffConcurrentStoreUseCase(
            staff_repository, store_repository, assignment, corporate_access
        ),
        remove_concurrent_store=RemoveStaffConcurrentStoreUseCase(
            staff_repository, store_repository, assignment, corporate_access
        ),
        activate=ActivateStaffUseCase(staff_repository, corporate_access),
        deactivate=DeactivateStaffUseCase(staff_repository, corporate_access),
    )
