"""スタッフ無効化・有効化ユースケースのテスト。"""

from __future__ import annotations

import pytest

from app.application.staff import (
    ActivateStaffCommand,
    ActivateStaffUseCase,
    DeactivateStaffCommand,
    DeactivateStaffUseCase,
)
from app.domain.corporate import CorporateId
from tests.application.access_helpers import create_vendor_corporate_access
from tests.factories.staff_factory import create_staff
from tests.fakes.in_memory_staff_repository import InMemoryStaffRepository


@pytest.mark.asyncio
async def test_deactivate_and_activate_staff_success() -> None:
    # Arrange
    staff_repo = InMemoryStaffRepository()
    corporate_access = create_vendor_corporate_access()
    deactivate_use_case = DeactivateStaffUseCase(
        repository=staff_repo,
        corporate_access=corporate_access,
    )
    activate_use_case = ActivateStaffUseCase(
        repository=staff_repo,
        corporate_access=corporate_access,
    )

    corp_id = CorporateId.generate()
    staff = create_staff(corporate_id=corp_id)
    await staff_repo.save(staff)

    assert staff.is_active is True

    # Act: 無効化（退職等）
    deactivate_cmd = DeactivateStaffCommand(
        corporate_id=str(corp_id.value),
        staff_id=str(staff.id.value),
    )
    await deactivate_use_case.execute(deactivate_cmd)

    # Assert
    deactivated = await staff_repo.get(corporate_id=corp_id, staff_id=staff.id)
    assert deactivated is not None
    assert deactivated.is_active is False

    # Act: 再有効化（復職等）
    activate_cmd = ActivateStaffCommand(
        corporate_id=str(corp_id.value),
        staff_id=str(staff.id.value),
    )
    await activate_use_case.execute(activate_cmd)

    # Assert
    reactivated = await staff_repo.get(corporate_id=corp_id, staff_id=staff.id)
    assert reactivated is not None
    assert reactivated.is_active is True
