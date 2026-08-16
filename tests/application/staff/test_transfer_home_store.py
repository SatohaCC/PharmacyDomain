"""主所属店舗異動ユースケースのテスト。"""

from __future__ import annotations

from datetime import date

import pytest

from app.application.staff import (
    StaffNotFoundError,
    TransferStaffHomeStoreCommand,
    TransferStaffHomeStoreUseCase,
)
from app.domain.corporate import CorporateId
from app.domain.staff import StaffStoreAssignmentService
from tests.application.access_helpers import create_vendor_corporate_access
from tests.factories.staff_factory import create_staff
from tests.factories.store_factory import create_store
from tests.fakes.in_memory_staff_repository import InMemoryStaffRepository
from tests.fakes.in_memory_store_repository import InMemoryStoreRepository


@pytest.mark.asyncio
async def test_transfer_home_store_success() -> None:
    # Arrange
    staff_repo = InMemoryStaffRepository()
    store_repo = InMemoryStoreRepository()
    assignment_service = StaffStoreAssignmentService()

    use_case = TransferStaffHomeStoreUseCase(
        staff_repository=staff_repo,
        store_repository=store_repo,
        assignment_service=assignment_service,
        corporate_access=create_vendor_corporate_access(),
    )

    corp_id = CorporateId.generate()
    staff = create_staff(corporate_id=corp_id)
    await staff_repo.save(staff)

    store_a = create_store(corporate_id=corp_id, name="店舗A")
    store_b = create_store(corporate_id=corp_id, name="店舗B")
    await store_repo.save(store_a)
    await store_repo.save(store_b)

    # 初回主所属
    cmd1 = TransferStaffHomeStoreCommand(
        corporate_id=str(corp_id.value),
        staff_id=str(staff.id.value),
        new_store_id=str(store_a.id.value),
        transfer_date=date(2026, 1, 1),
    )
    await use_case.execute(cmd1)

    # 店舗Bへ異動
    cmd2 = TransferStaffHomeStoreCommand(
        corporate_id=str(corp_id.value),
        staff_id=str(staff.id.value),
        new_store_id=str(store_b.id.value),
        transfer_date=date(2026, 4, 1),
    )

    # Act
    await use_case.execute(cmd2)

    # Assert
    updated = await staff_repo.get(corporate_id=corp_id, staff_id=staff.id)
    assert updated is not None
    assert updated.current_home_store_id(date(2026, 4, 1)) == store_b.id


@pytest.mark.asyncio
async def test_transfer_home_store_raises_staff_not_found_on_different_corporate() -> (
    None
):
    # Arrange
    staff_repo = InMemoryStaffRepository()
    store_repo = InMemoryStoreRepository()
    assignment_service = StaffStoreAssignmentService()

    use_case = TransferStaffHomeStoreUseCase(
        staff_repository=staff_repo,
        store_repository=store_repo,
        assignment_service=assignment_service,
        corporate_access=create_vendor_corporate_access(),
    )

    corp_a_id = CorporateId.generate()
    corp_b_id = CorporateId.generate()

    staff_a = create_staff(corporate_id=corp_a_id)
    await staff_repo.save(staff_a)

    store_b = create_store(corporate_id=corp_b_id)
    await store_repo.save(store_b)

    cmd = TransferStaffHomeStoreCommand(
        corporate_id=str(corp_b_id.value),  # 法人Bのコンテキストで法人Aのスタッフを指定
        staff_id=str(staff_a.id.value),
        new_store_id=str(store_b.id.value),
        transfer_date=date(2026, 4, 1),
    )

    # Act / Assert
    with pytest.raises(StaffNotFoundError):
        await use_case.execute(cmd)
