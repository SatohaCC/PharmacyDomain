"""スタッフ詳細取得ユースケースのテスト。"""

from __future__ import annotations

import pytest

from app.application.staff import GetStaffQuery, GetStaffUseCase, StaffNotFoundError
from app.domain.corporate import CorporateId
from app.domain.staff.primitives import StaffId
from tests.application.access_helpers import create_vendor_corporate_access
from tests.factories.staff_factory import create_staff
from tests.fakes.in_memory_staff_repository import InMemoryStaffRepository


@pytest.mark.asyncio
async def test_get_staff_success() -> None:
    # Arrange
    staff_repo = InMemoryStaffRepository()
    use_case = GetStaffUseCase(
        repository=staff_repo,
        corporate_access=create_vendor_corporate_access(),
    )

    corp_id = CorporateId.generate()
    staff = create_staff(corporate_id=corp_id, code="STF-100")
    await staff_repo.save(staff)

    query = GetStaffQuery(
        corporate_id=str(corp_id.value),
        staff_id=str(staff.id.value),
    )

    # Act
    dto = await use_case.execute(query)

    # Assert
    assert dto.id == str(staff.id.value)
    assert dto.corporate_id == str(corp_id.value)
    assert dto.code == "STF-100"
    assert dto.is_active is True


@pytest.mark.asyncio
async def test_get_staff_raises_error_when_staff_not_found() -> None:
    # Arrange
    staff_repo = InMemoryStaffRepository()
    use_case = GetStaffUseCase(
        repository=staff_repo,
        corporate_access=create_vendor_corporate_access(),
    )
    corp_id = CorporateId.generate()

    query = GetStaffQuery(
        corporate_id=str(corp_id.value),
        staff_id=str(StaffId.generate().value),
    )

    # Act / Assert: 存在しないスタッフは StaffNotFoundError となること
    with pytest.raises(StaffNotFoundError):
        await use_case.execute(query)
