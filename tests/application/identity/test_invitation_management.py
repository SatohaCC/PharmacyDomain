"""本人・期限・単回利用を含む招待発行と受諾。"""

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta

import pytest

from app.application.identity.management import (
    IdentityManagement,
    IdentityRepositories,
    InviteUserCommand,
)
from app.application.identity.resolve_actor import VerifiedIdentity
from app.domain.corporate.primitives import CorporateId
from app.domain.foundation.exceptions import DomainError
from app.domain.identity.account_person import AccountPerson
from app.domain.identity.invitation import InvitationStatus
from app.domain.identity.primitives import (
    AccountPersonId,
    MembershipRole,
    UserAccountId,
)
from app.domain.identity.user_account import UserAccount
from app.domain.shared.person_name import PersonNames
from tests.application.access_helpers import (
    AutoProvisioningCorporateRepository,
    create_vendor_corporate_access,
)
from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_organization_management import FakeOrganizationLock
from tests.fakes.in_memory_identity_repositories import (
    InMemoryAccountPersonRepository,
    InMemoryCorporateMembershipRepository,
    InMemoryStaffPersonLinkRepository,
    InMemoryUserAccountRepository,
    InMemoryUserInvitationRepository,
)
from tests.fakes.in_memory_staff_repository import InMemoryStaffRepository
from tests.fakes.in_memory_store_repository import InMemoryStoreRepository
from tests.fakes.null_unit_of_work import NullUnitOfWork


@dataclass
class Fixture:
    """招待の実UseCaseと保存結果を観測する。"""

    service: IdentityManagement
    repositories: IdentityRepositories
    clock: FakeClock
    person: AccountPerson
    command: InviteUserCommand


async def _setup() -> Fixture:
    repositories = IdentityRepositories(
        InMemoryAccountPersonRepository(),
        InMemoryUserAccountRepository(),
        InMemoryCorporateMembershipRepository(),
        InMemoryStaffPersonLinkRepository(),
        InMemoryUserInvitationRepository(),
    )
    person = AccountPerson(
        id=AccountPersonId.generate(),
        names=PersonNames.create(
            last_name="山田",
            first_name="太郎",
            last_name_kana="ヤマダ",
            first_name_kana="タロウ",
        ),
    )
    await repositories.people.save(person)
    clock = FakeClock(datetime(2026, 9, 17, tzinfo=UTC))
    service = IdentityManagement(
        repositories,
        InMemoryStaffRepository(),
        InMemoryStoreRepository(),
        create_vendor_corporate_access(),
        clock,
        NullUnitOfWork(),
        FakeOrganizationLock(),
        AutoProvisioningCorporateRepository(),
    )
    command = InviteUserCommand(
        corporate_id=str(CorporateId.generate().value),
        person_id=str(person.id.value),
        addressee="person@example.test",
        role=MembershipRole.CORPORATE_ADMIN,
        expires_at=clock.now() + timedelta(days=1),
    )
    return Fixture(service, repositories, clock, person, command)


@pytest.mark.asyncio
@pytest.mark.parametrize("existing_account", [False, True])
async def test_招待は本人の既存アカウントを再利用して一度だけ受諾できる(
    existing_account: bool,
) -> None:
    fixture = await _setup()
    original = UserAccount(id=UserAccountId.generate(), person_id=fixture.person.id)
    if existing_account:
        await fixture.repositories.accounts.save(original)
    issued = await fixture.service.invite(fixture.command)
    from app.domain.identity.primitives import UserInvitationId

    stored = await fixture.repositories.invitations.get(
        UserInvitationId.parse(issued.id)
    )
    assert stored is not None and stored.secret_digest.value != issued.secret
    identity = VerifiedIdentity(
        person_id=fixture.person.id, principal_id="issuer/verified-subject"
    )
    account = await fixture.service.accept(issued.secret, identity)
    assert account.person_id == fixture.person.id
    if existing_account:
        assert account.id == original.id
    membership = await fixture.repositories.memberships.find_active_for_account(
        account.id
    )
    assert (
        membership is not None
        and membership.corporate_id.value
        == CorporateId.parse(fixture.command.corporate_id).value
    )
    accepted = await fixture.repositories.invitations.get(stored.id)
    assert accepted is not None and accepted.status == InvitationStatus.ACCEPTED
    with pytest.raises(DomainError):
        await fixture.service.accept(issued.secret, identity)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "violation", ["別人", "期限一致", "期限超過", "取消", "秘密不一致"]
)
async def test_無効な招待受諾ではアカウントを作らない(violation: str) -> None:
    fixture = await _setup()
    issued = await fixture.service.invite(fixture.command)
    person_id = AccountPersonId.generate() if violation == "別人" else fixture.person.id
    if violation.startswith("期限"):
        fixture.clock.advance(
            timedelta(days=1, seconds=1 if violation == "期限超過" else 0)
        )
    if violation == "取消":
        from app.domain.identity.primitives import UserInvitationId

        stored = await fixture.repositories.invitations.get(
            UserInvitationId.parse(issued.id)
        )
        assert stored is not None
        await fixture.repositories.invitations.save(
            replace(stored, status=InvitationStatus.CANCELLED)
        )
    secret = "不正秘密" if violation == "秘密不一致" else issued.secret
    with pytest.raises(DomainError):
        await fixture.service.accept(
            secret,
            VerifiedIdentity(
                person_id=person_id, principal_id="issuer/verified-subject"
            ),
        )
    assert await fixture.repositories.accounts.get_by_person(fixture.person.id) is None


@pytest.mark.asyncio
async def test_招待を管理者が取り消すと本人も受諾できない() -> None:
    fixture = await _setup()
    issued = await fixture.service.invite(fixture.command)
    await fixture.service.cancel_invitation(fixture.command.corporate_id, issued.id)
    with pytest.raises(DomainError):
        await fixture.service.accept(
            issued.secret,
            VerifiedIdentity(
                person_id=fixture.person.id, principal_id="issuer/subject"
            ),
        )
