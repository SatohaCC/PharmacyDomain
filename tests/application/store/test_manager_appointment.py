"""管理薬剤師の任命が、スタッフと本人の対応を前提にすること。"""

from dataclasses import replace
from datetime import UTC, date, datetime

import pytest

from app.application.composition.staff_person_adapter import StaffPersonAdapter
from app.application.store.management import (
    ManagerAction,
    ManageStoreManagerCommand,
    ManageStoreManagerUseCase,
)
from app.domain.identity.staff_person_link import StaffPersonLink
from app.domain.shared.actor import AccountPersonId
from app.domain.staff.primitives import (
    AffiliationPeriod,
    PharmacistLicenseNumber,
    PharmacistProfile,
    StaffQualifications,
    StoreAffiliation,
)
from app.domain.staff.staff import Staff
from app.domain.store.manager_assignment import ManagerPersonUnresolvedError
from app.domain.store.store import Store
from tests.application.access_helpers import create_vendor_corporate_access
from tests.factories.staff_factory import create_staff
from tests.factories.store_factory import create_store
from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_organization_management import FakeOrganizationLock
from tests.fakes.in_memory_identity_repositories import (
    InMemoryStaffPersonLinkRepository,
)
from tests.fakes.in_memory_manager_assignment_repository import (
    InMemoryStoreManagerAssignmentRepository,
)
from tests.fakes.in_memory_staff_repository import InMemoryStaffRepository
from tests.fakes.in_memory_store_repository import InMemoryStoreRepository
from tests.fakes.null_unit_of_work import NullUnitOfWork


def _pharmacist(store: Store) -> Staff:
    return replace(
        create_staff(corporate_id=store.corporate_id),
        qualifications=StaffQualifications.from_profiles(
            PharmacistProfile(license_number=PharmacistLicenseNumber("654321"))
        ),
        affiliations=(
            StoreAffiliation(
                store_id=store.id,
                is_primary=True,
                period=AffiliationPeriod(start_date=date(2026, 1, 1)),
            ),
        ),
    )


async def _use_case(
    store: Store, staff: Staff, links: InMemoryStaffPersonLinkRepository
) -> ManageStoreManagerUseCase:
    stores = InMemoryStoreRepository()
    await stores.save(store)
    staff_repository = InMemoryStaffRepository()
    await staff_repository.save(staff)
    return ManageStoreManagerUseCase(
        stores,
        staff_repository,
        InMemoryStoreManagerAssignmentRepository(),
        StaffPersonAdapter(links),
        create_vendor_corporate_access(),
        FakeClock(datetime(2026, 9, 17, 2, tzinfo=UTC)),
        NullUnitOfWork(),
        FakeOrganizationLock(),
    )


def _command(store: Store, staff: Staff) -> ManageStoreManagerCommand:
    return ManageStoreManagerCommand(
        corporate_id=str(store.corporate_id.value),
        store_id=str(store.id.value),
        action=ManagerAction.APPOINT,
        staff_id=str(staff.id.value),
        starts_on=date(2026, 9, 1),
    )


@pytest.mark.asyncio
async def test_本人が固定されたスタッフを管理薬剤師に任命できる() -> None:
    # Arrange
    store = create_store()
    staff = _pharmacist(store)
    person_id = AccountPersonId.generate()
    links = InMemoryStaffPersonLinkRepository()
    await links.save(
        StaffPersonLink(
            id=staff.id, corporate_id=store.corporate_id, person_id=person_id
        )
    )
    use_case = await _use_case(store, staff, links)

    # Act
    result = await use_case.execute(_command(store, staff))

    # Assert
    assert result.staff_id == str(staff.id.value)


@pytest.mark.asyncio
async def test_本人の固定されていないスタッフは管理薬剤師に任命できない() -> None:
    """専任義務は自然人にかかるので、本人の分からない任命を作らせない。

    「分からないなら通す」に倒すと、その1件だけが兼務の検査をすり抜ける。
    """
    # Arrange
    store = create_store()
    staff = _pharmacist(store)
    use_case = await _use_case(store, staff, InMemoryStaffPersonLinkRepository())

    # Act & Assert
    with pytest.raises(ManagerPersonUnresolvedError):
        await use_case.execute(_command(store, staff))


@pytest.mark.asyncio
async def test_他法人で固定された対応は任命に使えない() -> None:
    """対応の法人が違えば、存在しないものとして扱う。"""
    # Arrange
    store = create_store()
    staff = _pharmacist(store)
    other = create_store()
    links = InMemoryStaffPersonLinkRepository()
    await links.save(
        StaffPersonLink(
            id=staff.id,
            corporate_id=other.corporate_id,
            person_id=AccountPersonId.generate(),
        )
    )
    use_case = await _use_case(store, staff, links)

    # Act & Assert
    with pytest.raises(ManagerPersonUnresolvedError):
        await use_case.execute(_command(store, staff))
