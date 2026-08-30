"""スタッフ無効化・有効化ユースケースのテスト。"""

from __future__ import annotations

from datetime import date

import pytest

from app.application.staff import (
    ActivateStaffCommand,
    ActivateStaffUseCase,
    DeactivateStaffCommand,
    DeactivateStaffUseCase,
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
        retired_on=date(2026, 3, 31),
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


@pytest.mark.asyncio
async def test_無効化した退職者は_退職日の翌日以降の主所属店舗を返さない() -> None:
    """退職を経ても、在籍していた過去日の所属は引き続き引ける。

    退職日を所属履歴へ書き込むことで解決しているため、導出は適用日ごとの
    判定のまま保たれる。``is_active`` で導出を打ち切る実装だと、過去日の
    問い合わせまで ``None`` になり調剤録の追跡が切れる。
    """
    # Arrange
    staff_repo = InMemoryStaffRepository()
    store_repo = InMemoryStoreRepository()
    corporate_access = create_vendor_corporate_access()
    transfer_use_case = TransferStaffHomeStoreUseCase(
        staff_repository=staff_repo,
        store_repository=store_repo,
        assignment_service=StaffStoreAssignmentService(),
        corporate_access=corporate_access,
    )
    deactivate_use_case = DeactivateStaffUseCase(
        repository=staff_repo,
        corporate_access=corporate_access,
    )

    corp_id = CorporateId.generate()
    staff = create_staff(corporate_id=corp_id)
    await staff_repo.save(staff)
    store = create_store(corporate_id=corp_id, name="店舗A")
    await store_repo.save(store)

    await transfer_use_case.execute(
        TransferStaffHomeStoreCommand(
            corporate_id=str(corp_id.value),
            staff_id=str(staff.id.value),
            new_store_id=str(store.id.value),
            transfer_date=date(2026, 1, 1),
        )
    )

    # Act
    await deactivate_use_case.execute(
        DeactivateStaffCommand(
            corporate_id=str(corp_id.value),
            staff_id=str(staff.id.value),
            retired_on=date(2026, 3, 31),
        )
    )

    # Assert
    retired = await staff_repo.get(corporate_id=corp_id, staff_id=staff.id)
    assert retired is not None
    assert retired.current_home_store_id(date(2026, 2, 1)) == store.id
    assert retired.current_home_store_id(date(2026, 3, 31)) == store.id
    assert retired.current_home_store_id(date(2026, 4, 1)) is None
