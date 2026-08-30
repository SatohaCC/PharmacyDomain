"""スタッフコンテキストのユースケース束。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.common.clock import Clock
from app.application.corporate.corporate_access import CorporateAccessService
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
from app.domain.staff.services import (
    StaffCodeUniquenessService,
    StaffStoreAssignmentService,
)
from app.infrastructure.composition.repositories import PostgresRepositorySet


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
