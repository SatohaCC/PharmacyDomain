"""スタッフ新規登録ユースケースのテスト。"""

from __future__ import annotations

from datetime import date

import pytest

from app.application.corporate import CorporateInactiveError
from app.application.staff import RegisterStaffCommand, RegisterStaffUseCase
from app.domain.corporate import CorporateId
from app.domain.staff import (
    StaffCodeAlreadyExistsError,
    StaffCodeUniquenessService,
    StaffStoreAssignmentService,
)
from tests.application.access_helpers import (
    AutoProvisioningCorporateRepository,
    create_vendor_corporate_access,
    create_vendor_corporate_access_for,
)
from tests.factories.store_factory import create_store
from tests.fakes.in_memory_staff_repository import InMemoryStaffRepository
from tests.fakes.in_memory_store_repository import InMemoryStoreRepository


@pytest.mark.asyncio
async def test_register_staff_success() -> None:
    # Arrange
    staff_repo = InMemoryStaffRepository()
    store_repo = InMemoryStoreRepository()
    uniqueness_service = StaffCodeUniquenessService(staff_repo)
    assignment_service = StaffStoreAssignmentService()

    use_case = RegisterStaffUseCase(
        staff_repository=staff_repo,
        store_repository=store_repo,
        uniqueness_service=uniqueness_service,
        assignment_service=assignment_service,
        corporate_access=create_vendor_corporate_access(),
    )

    corp_id = CorporateId.generate()
    store = create_store(corporate_id=corp_id)
    await store_repo.save(store)

    cmd = RegisterStaffCommand(
        corporate_id=str(corp_id.value),
        last_name="山田",
        first_name="太郎",
        last_name_kana="ヤマダ",
        first_name_kana="タロウ",
        code="STF-001",
        initial_home_store_id=str(store.id.value),
        initial_start_date=date(2026, 4, 1),
    )

    # Act
    created_staff = await use_case.execute(cmd)

    # Assert
    assert created_staff is not None
    assert created_staff.code is not None
    assert created_staff.code.value == "STF-001"
    assert created_staff.current_home_store_id(date(2026, 4, 1)) == store.id

    fetched = await staff_repo.get(corporate_id=corp_id, staff_id=created_staff.id)
    assert fetched is not None


@pytest.mark.asyncio
async def test_register_staff_rejects_inactive_corporate() -> None:
    # Arrange
    staff_repo = InMemoryStaffRepository()
    store_repo = InMemoryStoreRepository()
    corporate_id = CorporateId.generate()
    corporate_repository = AutoProvisioningCorporateRepository()
    corporate_repository.set_inactive(corporate_id)
    use_case = RegisterStaffUseCase(
        staff_repository=staff_repo,
        store_repository=store_repo,
        uniqueness_service=StaffCodeUniquenessService(staff_repo),
        assignment_service=StaffStoreAssignmentService(),
        corporate_access=create_vendor_corporate_access_for(corporate_repository),
    )
    command = RegisterStaffCommand(
        corporate_id=str(corporate_id.value),
        last_name="山田",
        first_name="太郎",
        last_name_kana="ヤマダ",
        first_name_kana="タロウ",
        code="STF-001",
    )

    # Act & Assert
    with pytest.raises(CorporateInactiveError):
        await use_case.execute(command)

    assert await staff_repo.list_all() == []


@pytest.mark.asyncio
async def test_register_staff_with_pharmacist_qualification() -> None:
    # Arrange
    staff_repo = InMemoryStaffRepository()
    store_repo = InMemoryStoreRepository()
    uniqueness_service = StaffCodeUniquenessService(staff_repo)
    assignment_service = StaffStoreAssignmentService()

    use_case = RegisterStaffUseCase(
        staff_repository=staff_repo,
        store_repository=store_repo,
        uniqueness_service=uniqueness_service,
        assignment_service=assignment_service,
        corporate_access=create_vendor_corporate_access(),
    )

    corp_id = CorporateId.generate()

    cmd = RegisterStaffCommand(
        corporate_id=str(corp_id.value),
        last_name="佐藤",
        first_name="花子",
        last_name_kana="サトウ",
        first_name_kana="ハナコ",
        code="PHARM-001",
        pharmacist_license_number="123456",
        insurance_pharmacist_registration_number="REG-789",
        insurance_pharmacist_registration_date=date(2020, 4, 1),
    )

    # Act
    created_staff = await use_case.execute(cmd)

    # Assert
    assert created_staff.is_pharmacist is True
    assert created_staff.pharmacist_profile is not None
    assert created_staff.pharmacist_profile.license_number.value == "123456"
    assert created_staff.pharmacist_profile.can_bill_insurance() is True


@pytest.mark.asyncio
async def test_register_staff_raises_error_on_duplicate_code() -> None:
    # Arrange
    staff_repo = InMemoryStaffRepository()
    store_repo = InMemoryStoreRepository()
    uniqueness_service = StaffCodeUniquenessService(staff_repo)
    assignment_service = StaffStoreAssignmentService()

    use_case = RegisterStaffUseCase(
        staff_repository=staff_repo,
        store_repository=store_repo,
        uniqueness_service=uniqueness_service,
        assignment_service=assignment_service,
        corporate_access=create_vendor_corporate_access(),
    )

    corp_id = CorporateId.generate()
    cmd1 = RegisterStaffCommand(
        corporate_id=str(corp_id.value),
        last_name="山田",
        first_name="太郎",
        last_name_kana="ヤマダ",
        first_name_kana="タロウ",
        code="STF-001",
    )
    await use_case.execute(cmd1)

    cmd2 = RegisterStaffCommand(
        corporate_id=str(corp_id.value),
        last_name="佐藤",
        first_name="次郎",
        last_name_kana="サトウ",
        first_name_kana="ジロウ",
        code="STF-001",
    )

    # Act / Assert
    with pytest.raises(StaffCodeAlreadyExistsError):
        await use_case.execute(cmd2)
