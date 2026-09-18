"""退職に伴うアクセス権の失効を確認する。"""

from datetime import UTC, date, datetime

import pytest

from app.application.composition.staff_integrity import ManagedStaffRepository
from app.domain.identity.membership import CorporateMembership
from app.domain.identity.primitives import (
    AccountPersonId,
    AccountStatus,
    CorporateMembershipId,
    MembershipRole,
    UserAccountId,
)
from app.domain.identity.user_account import UserAccount
from tests.factories.staff_factory import create_staff
from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_organization_management import FakeOrganizationLock
from tests.fakes.in_memory_identity_repositories import (
    InMemoryCorporateMembershipRepository,
    InMemoryUserAccountRepository,
)
from tests.fakes.in_memory_manager_assignment_repository import (
    InMemoryStoreManagerAssignmentRepository,
)
from tests.fakes.in_memory_staff_repository import InMemoryStaffRepository
from tests.fakes.in_memory_store_repository import InMemoryStoreRepository
from tests.fakes.null_unit_of_work import NullUnitOfWork


@pytest.mark.asyncio
async def test_退職は法人アクセス権を停止し再雇用では権限を復活させない() -> None:
    raw = InMemoryStaffRepository()
    staff = create_staff()
    await raw.save(staff)
    account = UserAccount(
        id=UserAccountId.generate(), person_id=AccountPersonId.generate()
    )
    accounts = InMemoryUserAccountRepository()
    await accounts.save(account)
    memberships = InMemoryCorporateMembershipRepository()
    membership = CorporateMembership(
        id=CorporateMembershipId.generate(),
        account_id=account.id,
        corporate_id=staff.corporate_id,
        role=MembershipRole.STORE_OPERATOR,
        store_ids=frozenset(),
        staff_id=staff.id,
    )
    await memberships.save(membership)
    repository = ManagedStaffRepository(
        raw,
        InMemoryStoreRepository(),
        InMemoryStoreManagerAssignmentRepository(),
        memberships,
        accounts,
        FakeClock(datetime(2026, 9, 17, tzinfo=UTC)),
        NullUnitOfWork(),
        FakeOrganizationLock(),
    )
    await repository.save(staff.deactivate(date(2026, 9, 17)))
    actual = await memberships.get(membership.id)
    assert actual is not None and actual.status == AccountStatus.SUSPENDED
    unchanged = await accounts.get(account.id)
    assert unchanged is not None and unchanged.status == AccountStatus.ACTIVE
    await repository.save(staff.activate())
    actual = await memberships.get(membership.id)
    assert actual is not None and actual.status == AccountStatus.SUSPENDED
