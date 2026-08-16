"""スタッフ一覧取得ユースケースのテスト。"""

from __future__ import annotations

import pytest

from app.application.staff import ListStaffsQuery, ListStaffsUseCase
from app.domain.corporate import CorporateId
from tests.application.access_helpers import create_vendor_corporate_access
from tests.factories.staff_factory import create_staff
from tests.fakes.in_memory_staff_repository import InMemoryStaffRepository


@pytest.mark.asyncio
async def test_list_staffs_returns_only_matching_corporate_staffs() -> None:
    # Arrange
    staff_repo = InMemoryStaffRepository()
    use_case = ListStaffsUseCase(
        repository=staff_repo,
        corporate_access=create_vendor_corporate_access(),
    )

    corp_a_id = CorporateId.generate()
    corp_b_id = CorporateId.generate()

    staff_a1 = create_staff(corporate_id=corp_a_id, code="STF-A1")
    staff_a2 = create_staff(corporate_id=corp_a_id, code="STF-A2")
    staff_b1 = create_staff(corporate_id=corp_b_id, code="STF-B1")

    await staff_repo.save(staff_a1)
    await staff_repo.save(staff_a2)
    await staff_repo.save(staff_b1)

    query = ListStaffsQuery(corporate_id=str(corp_a_id.value))

    # Act
    dtos = await use_case.execute(query)

    # Assert
    assert len(dtos) == 2
    codes = {dto.code for dto in dtos}
    assert codes == {"STF-A1", "STF-A2"}
