"""スタッフ資格情報更新ユースケースのテスト。"""

from __future__ import annotations

from datetime import date

import pytest

from app.application.staff import (
    UpdateStaffQualificationsCommand,
    UpdateStaffQualificationsUseCase,
)
from app.domain.corporate import CorporateId
from tests.application.access_helpers import create_vendor_corporate_access
from tests.factories.staff_factory import create_staff
from tests.fakes.in_memory_staff_repository import InMemoryStaffRepository


@pytest.mark.asyncio
async def test_update_staff_qualifications_success() -> None:
    # Arrange
    staff_repo = InMemoryStaffRepository()
    use_case = UpdateStaffQualificationsUseCase(
        repository=staff_repo,
        corporate_access=create_vendor_corporate_access(),
    )

    corp_id = CorporateId.generate()
    staff = create_staff(corporate_id=corp_id)
    await staff_repo.save(staff)

    assert staff.is_pharmacist is False

    cmd = UpdateStaffQualificationsCommand(
        corporate_id=str(corp_id.value),
        staff_id=str(staff.id.value),
        pharmacist_license_number="654321",
        insurance_pharmacist_registration_number="REG-999",
        insurance_pharmacist_registration_date=date(2026, 4, 1),
    )

    # Act
    await use_case.execute(cmd)

    # Assert
    updated_staff = await staff_repo.get(corporate_id=corp_id, staff_id=staff.id)
    assert updated_staff is not None
    assert updated_staff.is_pharmacist is True
    assert updated_staff.pharmacist_profile is not None
    assert updated_staff.pharmacist_profile.license_number.value == "654321"
    assert updated_staff.pharmacist_profile.can_bill_insurance() is True
