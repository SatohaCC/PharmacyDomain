"""スタッフアプリケーション層（ユースケース）。"""

from app.application.staff.activate_staff import (
    ActivateStaffCommand,
    ActivateStaffUseCase,
)
from app.application.staff.assign_concurrent_store import (
    AssignStaffConcurrentStoreCommand,
    AssignStaffConcurrentStoreUseCase,
)
from app.application.staff.change_staff_job_title import (
    ChangeStaffJobTitleCommand,
    ChangeStaffJobTitleUseCase,
)
from app.application.staff.change_staff_names import (
    ChangeStaffNamesCommand,
    ChangeStaffNamesUseCase,
)
from app.application.staff.deactivate_staff import (
    DeactivateStaffCommand,
    DeactivateStaffUseCase,
)
from app.application.staff.exceptions import (
    StaffApplicationError,
    StaffNotFoundError,
)
from app.application.staff.get_staff import (
    GetStaffQuery,
    GetStaffUseCase,
    StaffDto,
)
from app.application.staff.list_staffs import (
    ListStaffsQuery,
    ListStaffsUseCase,
    StaffSummaryDto,
)
from app.application.staff.register_staff import (
    RegisterStaffCommand,
    RegisterStaffUseCase,
)
from app.application.staff.remove_concurrent_store import (
    RemoveStaffConcurrentStoreCommand,
    RemoveStaffConcurrentStoreUseCase,
)
from app.application.staff.transfer_home_store import (
    TransferStaffHomeStoreCommand,
    TransferStaffHomeStoreUseCase,
)
from app.application.staff.update_qualifications import (
    UpdateStaffQualificationsCommand,
    UpdateStaffQualificationsUseCase,
)

__all__ = [
    "ActivateStaffCommand",
    "ActivateStaffUseCase",
    "AssignStaffConcurrentStoreCommand",
    "AssignStaffConcurrentStoreUseCase",
    "ChangeStaffJobTitleCommand",
    "ChangeStaffJobTitleUseCase",
    "ChangeStaffNamesCommand",
    "ChangeStaffNamesUseCase",
    "DeactivateStaffCommand",
    "DeactivateStaffUseCase",
    "GetStaffQuery",
    "GetStaffUseCase",
    "ListStaffsQuery",
    "ListStaffsUseCase",
    "RegisterStaffCommand",
    "RegisterStaffUseCase",
    "RemoveStaffConcurrentStoreCommand",
    "RemoveStaffConcurrentStoreUseCase",
    "StaffApplicationError",
    "StaffDto",
    "StaffNotFoundError",
    "StaffSummaryDto",
    "TransferStaffHomeStoreCommand",
    "TransferStaffHomeStoreUseCase",
    "UpdateStaffQualificationsCommand",
    "UpdateStaffQualificationsUseCase",
]
