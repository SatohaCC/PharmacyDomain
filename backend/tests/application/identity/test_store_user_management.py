"""管理薬剤師による更新が、自店舗の利用権限だけに閉じることを検証する。"""

from dataclasses import dataclass, replace
from datetime import date

import pytest

from app.application.access_control.boundary_models import (
    ActorContext,
    ActorRole,
    ResolvedActorContext,
)
from app.application.access_control.policies import AuthorizationService
from app.application.common.exceptions import AuthorizationError, NotFoundError
from app.application.corporate.commands.services.corporate_access import (
    CorporateAccessService,
)
from app.application.identity.commands.change_membership import ChangeMembershipUseCase
from app.application.identity.commands.services.repositories import IdentityRepositories
from app.application.identity.commands.suspend_account import SuspendAccountUseCase
from app.domain.corporate.identifiers import CorporateId
from app.domain.identity.entities import CorporateMembership, UserAccount
from app.domain.identity.identifiers import CorporateMembershipId
from app.domain.identity.primitives import AccountStatus, MembershipRole
from app.domain.shared.actor import AccountPersonId, UserAccountId
from app.domain.staff.identifiers import StaffId
from app.domain.store.entities import StoreManagerAssignment
from app.domain.store.identifiers import StoreId
from tests.application.access_helpers import AutoProvisioningCorporateRepository
from tests.application.identity.helpers import create_identity_use_cases
from tests.factories.store_factory import create_manager_assignment, create_store
from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_organization_management import FakeOrganizationLock
from tests.fakes.in_memory_manager_assignment_repository import (
    InMemoryStoreManagerAssignmentRepository,
)
from tests.fakes.null_unit_of_work import NullUnitOfWork


@dataclass
class Fixture:
    """実アカウント・所属・任命と、同じ保存境界の更新操作。"""

    use_case: ChangeMembershipUseCase
    repositories: IdentityRepositories
    managers: InMemoryStoreManagerAssignmentRepository
    assignment: StoreManagerAssignment
    membership: CorporateMembership
    actor: ResolvedActorContext
    access: CorporateAccessService


async def _setup() -> Fixture:
    service = create_identity_use_cases()
    corporate = CorporateId.generate()
    own = create_store(corporate_id=corporate, name="テスト担当店舗")
    other = create_store(corporate_id=corporate, name="テスト他店舗")
    await service.stores.save(own)
    await service.stores.save(other)
    account = UserAccount(
        id=UserAccountId.generate(),
        corporate_id=corporate,
        person_id=AccountPersonId.generate(),
    )
    membership = CorporateMembership(
        id=CorporateMembershipId.generate(),
        corporate_id=corporate,
        account_id=account.id,
        role=MembershipRole.CORPORATE_ADMIN,
        store_ids=frozenset({own.id, other.id}),
    )
    await service.repositories.accounts.save(account)
    await service.repositories.memberships.save(membership)
    manager = UserAccount(
        id=UserAccountId.generate(),
        corporate_id=corporate,
        person_id=AccountPersonId.generate(),
    )
    manager_membership = CorporateMembership(
        id=CorporateMembershipId.generate(),
        corporate_id=corporate,
        account_id=manager.id,
        role=MembershipRole.STORE_OPERATOR,
        store_ids=frozenset({own.id}),
        staff_id=StaffId.generate(),
    )
    await service.repositories.accounts.save(manager)
    await service.repositories.memberships.save(manager_membership)
    assert manager_membership.staff_id is not None
    assignment = create_manager_assignment(
        corporate_id=corporate,
        store_id=own.id,
        staff_id=manager_membership.staff_id,
        person_id=manager.person_id,
        starts_on=date(2026, 8, 1),
    )
    managers = InMemoryStoreManagerAssignmentRepository()
    await managers.save(assignment)
    actor = ResolvedActorContext(
        principal_id="テスト管理薬剤師",
        roles=frozenset({ActorRole.STORE_OPERATOR, ActorRole.STORE_MANAGER}),
        corporate_id=corporate,
        person_id=manager.person_id,
        account_id=manager.id,
        membership_id=manager_membership.id,
        staff_id=manager_membership.staff_id,
        store_ids=frozenset({own.id}),
        managed_store_ids=frozenset({own.id}),
    )
    access = CorporateAccessService(
        AutoProvisioningCorporateRepository(), AuthorizationService(actor)
    )
    use_case = ChangeMembershipUseCase(
        service.repositories,
        service.staff,
        service.stores,
        access,
        NullUnitOfWork(),
        FakeOrganizationLock(),
        managers,
        FakeClock(),
    )
    return Fixture(
        use_case, service.repositories, managers, assignment, membership, actor, access
    )


@pytest.mark.asyncio
async def test_管理薬剤師_複数店舗利用の法人管理者を編集しても_自店舗だけを停止する() -> (
    None
):
    # Arrange
    fixture = await _setup()
    membership = fixture.membership
    # Act
    await fixture.use_case.execute(
        str(membership.corporate_id.value),
        str(membership.id.value),
        store_id=str(fixture.assignment.store_id.value),
        store_is_active=False,
    )
    # Assert
    updated = await fixture.repositories.memberships.get(membership.id)
    assert updated is not None
    assert updated.role == MembershipRole.CORPORATE_ADMIN
    assert updated.status == AccountStatus.ACTIVE
    assert updated.active_store_ids == membership.store_ids - {
        fixture.assignment.store_id
    }
    account = await fixture.repositories.accounts.get(membership.account_id)
    assert account is not None and account.status == AccountStatus.ACTIVE


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "change", ["role", "status", "other_store", "own_account", "expired", "own_store"]
)
async def test_管理薬剤師_担当範囲外や失効後の更新は_拒否して保存しない(
    change: str,
) -> None:
    # Arrange
    fixture = await _setup()
    membership = fixture.membership
    store = fixture.assignment.store_id
    role = MembershipRole.STORE_VIEWER if change == "role" else None
    status = AccountStatus.SUSPENDED if change == "status" else None
    stores = (
        (str(store.value), str(StoreId.generate().value))
        if change == "other_store"
        else None
    )
    target = fixture.actor.membership_id if change == "own_store" else membership.id
    assert target is not None
    if change == "expired":
        await fixture.managers.save(
            replace(
                fixture.assignment,
                period=replace(fixture.assignment.period, ends_on=date(2026, 8, 22)),
            )
        )
    # Act / Assert
    with pytest.raises(AuthorizationError):
        if change == "own_account":
            await SuspendAccountUseCase(
                fixture.repositories,
                fixture.access,
                NullUnitOfWork(),
                FakeOrganizationLock(),
            ).execute(str(membership.account_id.value))
        else:
            await fixture.use_case.execute(
                str(membership.corporate_id.value),
                str(target.value),
                role=role,
                status=status,
                store_ids=stores,
                store_id=str(store.value),
                store_is_active=False,
            )
    assert await fixture.repositories.memberships.get(membership.id) == membership


@pytest.mark.asyncio
@pytest.mark.parametrize("foreign", [False, True])
async def test_法人管理者_アカウント停止は_自法人のユーザーだけ許可する(
    foreign: bool,
) -> None:
    # Arrange
    fixture = await _setup()
    membership = replace(fixture.membership, status=AccountStatus.SUSPENDED)
    await fixture.repositories.memberships.save(membership)
    actor = ActorContext.corporate_admin(
        principal_id="テスト法人管理者",
        corporate_id=CorporateId.generate() if foreign else membership.corporate_id,
    )
    access = CorporateAccessService(
        AutoProvisioningCorporateRepository(), AuthorizationService(actor)
    )
    use_case = SuspendAccountUseCase(
        fixture.repositories, access, NullUnitOfWork(), FakeOrganizationLock()
    )
    # Act / Assert
    if foreign:
        with pytest.raises(NotFoundError):
            await use_case.execute(str(membership.account_id.value))
    else:
        await use_case.execute(str(membership.account_id.value))
    actual = await fixture.repositories.accounts.get(membership.account_id)
    assert actual is not None
    assert actual.status == (
        AccountStatus.ACTIVE if foreign else AccountStatus.SUSPENDED
    )
