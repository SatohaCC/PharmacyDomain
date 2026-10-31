"""スタッフ新規登録ユースケースのテスト。"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

import pytest

from app.application.composition.adapters.organization_snapshot_mapping import (
    StaffStoreAdapter,
)
from app.application.composition.adapters.staff_account_registration import (
    StaffAccountRegistrationAdapter,
)
from app.application.corporate.errors import CorporateInactiveError
from app.application.staff.commands.register_staff import (
    BulkStaffAccountInput,
    RegisterStaffCommand,
    RegisterStaffUseCase,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.staff.exceptions import StaffCodeAlreadyExistsError
from app.domain.staff.identifiers import StaffId
from app.domain.staff.services import (
    StaffCodeUniquenessService,
    StaffStoreAssignmentService,
)
from tests.application.access_helpers import (
    AutoProvisioningCorporateRepository,
    create_vendor_corporate_access,
    create_vendor_corporate_access_for,
)
from tests.factories.store_factory import create_store
from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_organization_management import FakeOrganizationLock
from tests.fakes.in_memory_identity_repositories import (
    FakeCredentialWriter,
    InMemoryAccountPersonRepository,
    InMemoryCorporateMembershipRepository,
    InMemoryStaffPersonLinkRepository,
    InMemoryUserAccountRepository,
)
from tests.fakes.in_memory_manager_assignment_repository import (
    InMemoryStoreManagerAssignmentRepository,
)
from tests.fakes.in_memory_staff_repository import InMemoryStaffRepository
from tests.fakes.in_memory_store_repository import InMemoryStoreRepository
from tests.fakes.null_unit_of_work import NullUnitOfWork


def _build_use_case(
    staff_repo: InMemoryStaffRepository,
    store_repo: InMemoryStoreRepository,
    access: Any = None,
) -> RegisterStaffUseCase:
    people = InMemoryAccountPersonRepository()
    accounts = InMemoryUserAccountRepository()
    memberships = InMemoryCorporateMembershipRepository()
    links = InMemoryStaffPersonLinkRepository()
    credentials = FakeCredentialWriter()
    adapter = StaffAccountRegistrationAdapter(
        people=people,
        accounts=accounts,
        memberships=memberships,
        links=links,
        credentials=credentials,
    )
    return RegisterStaffUseCase(
        staff_repository=staff_repo,
        store_repository=StaffStoreAdapter(store_repo),
        uniqueness_service=StaffCodeUniquenessService(staff_repo),
        assignment_service=StaffStoreAssignmentService(),
        corporate_access=access or create_vendor_corporate_access(),
        account_registration=adapter,
        unit_of_work=NullUnitOfWork(),
        lock=FakeOrganizationLock(),
        clock=FakeClock(datetime(2026, 4, 1, tzinfo=UTC)),
        store_managers=InMemoryStoreManagerAssignmentRepository(),
    )


def _default_account() -> BulkStaffAccountInput:
    return BulkStaffAccountInput(
        email="staff@example.test",
        password="Password123456789",
    )


@pytest.mark.asyncio
async def test_register_staff_success() -> None:
    # Arrange
    staff_repo = InMemoryStaffRepository()
    store_repo = InMemoryStoreRepository()
    use_case = _build_use_case(staff_repo, store_repo)

    corp_id = CorporateId.generate()
    store = create_store(corporate_id=corp_id)
    await store_repo.save(store)

    cmd = RegisterStaffCommand(
        corporate_id=str(corp_id.value),
        last_name="山田",
        first_name="太郎",
        last_name_kana="ヤマダ",
        first_name_kana="タロウ",
        account=_default_account(),
        code="STF-001",
        initial_home_store_id=str(store.id.value),
        initial_start_date=date(2026, 4, 1),
    )

    # Act
    result = await use_case.execute(cmd)

    # Assert
    staff_id = StaffId.parse(result.staff_id)
    created_staff = await staff_repo.get(corporate_id=corp_id, staff_id=staff_id)
    assert created_staff is not None
    assert created_staff.code is not None
    assert created_staff.code.value == "STF-001"
    assert created_staff.current_home_store_id(date(2026, 4, 1)) == store.id


@pytest.mark.asyncio
async def test_register_staff_rejects_inactive_corporate() -> None:
    # Arrange
    staff_repo = InMemoryStaffRepository()
    store_repo = InMemoryStoreRepository()
    corporate_id = CorporateId.generate()
    corporate_repository = AutoProvisioningCorporateRepository()
    corporate_repository.set_inactive(corporate_id)
    use_case = _build_use_case(
        staff_repo,
        store_repo,
        access=create_vendor_corporate_access_for(corporate_repository),
    )
    command = RegisterStaffCommand(
        corporate_id=str(corporate_id.value),
        last_name="山田",
        first_name="太郎",
        last_name_kana="ヤマダ",
        first_name_kana="タロウ",
        account=_default_account(),
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
    use_case = _build_use_case(staff_repo, store_repo)

    corp_id = CorporateId.generate()

    cmd = RegisterStaffCommand(
        corporate_id=str(corp_id.value),
        last_name="佐藤",
        first_name="花子",
        last_name_kana="サトウ",
        first_name_kana="ハナコ",
        account=_default_account(),
        code="PHARM-001",
        pharmacist_license_number="123456",
        insurance_pharmacist_registration_number="REG-789",
        insurance_pharmacist_registration_date=date(2020, 4, 1),
    )

    # Act
    result = await use_case.execute(cmd)

    # Assert
    staff_id = StaffId.parse(result.staff_id)
    created_staff = await staff_repo.get(corporate_id=corp_id, staff_id=staff_id)
    assert created_staff is not None
    assert created_staff.is_pharmacist is True
    assert created_staff.pharmacist_profile is not None
    assert created_staff.pharmacist_profile.license_number.value == "123456"
    assert created_staff.pharmacist_profile.can_bill_insurance() is True


@pytest.mark.asyncio
async def test_register_staff_raises_error_on_duplicate_code() -> None:
    # Arrange
    staff_repo = InMemoryStaffRepository()
    store_repo = InMemoryStoreRepository()
    use_case = _build_use_case(staff_repo, store_repo)

    corp_id = CorporateId.generate()
    cmd1 = RegisterStaffCommand(
        corporate_id=str(corp_id.value),
        last_name="山田",
        first_name="太郎",
        last_name_kana="ヤマダ",
        first_name_kana="タロウ",
        account=BulkStaffAccountInput(
            email="staff1@example.test",
            password="Password123456789",
        ),
        code="STF-001",
    )
    await use_case.execute(cmd1)

    cmd2 = RegisterStaffCommand(
        corporate_id=str(corp_id.value),
        last_name="佐藤",
        first_name="次郎",
        last_name_kana="サトウ",
        first_name_kana="ジロウ",
        account=BulkStaffAccountInput(
            email="staff2@example.test",
            password="Password123456789",
        ),
        code="STF-001",
    )

    # Act / Assert
    with pytest.raises(StaffCodeAlreadyExistsError):
        await use_case.execute(cmd2)
