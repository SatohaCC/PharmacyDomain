"""スタッフの労働契約変更および休職・復職ユースケースのテスト。"""

from __future__ import annotations

from datetime import date

from app.application.staff.commands.manage_staff_leave import (
    ReturnStaffFromLeaveCommand,
    ReturnStaffFromLeaveUseCase,
    StartStaffLeaveCommand,
    StartStaffLeaveUseCase,
)
from app.application.staff.commands.update_staff_employment import (
    UpdateStaffEmploymentCommand,
    UpdateStaffEmploymentUseCase,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.staff.primitives import EmploymentType, LeaveReason, StaffStatus
from tests.application.access_helpers import create_vendor_corporate_access
from tests.factories.staff_factory import create_staff
from tests.fakes.in_memory_staff_repository import InMemoryStaffRepository


async def test_update_staff_employment_success() -> None:
    # Arrange
    staff_repo = InMemoryStaffRepository()
    corporate_id = CorporateId.generate()
    staff = create_staff(corporate_id=corporate_id)
    await staff_repo.save(staff)

    use_case = UpdateStaffEmploymentUseCase(
        repository=staff_repo,
        corporate_access=create_vendor_corporate_access(),
    )

    # Act
    await use_case.execute(
        UpdateStaffEmploymentCommand(
            corporate_id=str(corporate_id.value),
            staff_id=str(staff.id.value),
            employment_type="part_time",
            weekly_contract_hours=24.5,
        )
    )

    # Assert
    updated = await staff_repo.get(corporate_id=corporate_id, staff_id=staff.id)
    assert updated is not None
    assert updated.employment_type == EmploymentType.PART_TIME
    assert updated.weekly_contract_hours is not None
    assert float(updated.weekly_contract_hours.value) == 24.5


async def test_manage_staff_leave_and_return_success() -> None:
    # Arrange
    staff_repo = InMemoryStaffRepository()
    corporate_id = CorporateId.generate()
    staff = create_staff(corporate_id=corporate_id)
    await staff_repo.save(staff)

    start_leave_use_case = StartStaffLeaveUseCase(
        repository=staff_repo,
        corporate_access=create_vendor_corporate_access(),
    )
    return_leave_use_case = ReturnStaffFromLeaveUseCase(
        repository=staff_repo,
        corporate_access=create_vendor_corporate_access(),
    )

    # Act 1: 休職開始
    await start_leave_use_case.execute(
        StartStaffLeaveCommand(
            corporate_id=str(corporate_id.value),
            staff_id=str(staff.id.value),
            leave_reason="childcare",
            left_on=date(2026, 4, 1),
        )
    )

    # Assert 1
    updated = await staff_repo.get(corporate_id=corporate_id, staff_id=staff.id)
    assert updated is not None
    assert updated.status == StaffStatus.ON_LEAVE
    assert updated.leave_reason == LeaveReason.CHILDCARE
    assert not updated.is_active

    # Act 2: 復職
    await return_leave_use_case.execute(
        ReturnStaffFromLeaveCommand(
            corporate_id=str(corporate_id.value),
            staff_id=str(staff.id.value),
        )
    )

    # Assert 2
    returned = await staff_repo.get(corporate_id=corporate_id, staff_id=staff.id)
    assert returned is not None
    assert returned.status == StaffStatus.ACTIVE
    assert returned.leave_reason is None
    assert returned.is_active
