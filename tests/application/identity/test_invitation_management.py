"""本人・期限・単回利用を含む招待発行と受諾。"""

from dataclasses import dataclass, replace
from datetime import timedelta

import pytest

from app.application.identity.invite_user import InviteUserCommand
from app.application.identity.resolve_actor import VerifiedIdentity
from app.application.identity.support import IdentityRepositories
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
from tests.application.identity.helpers import (
    IdentityUseCaseSet,
    create_identity_use_cases,
)
from tests.fakes.fake_clock import FakeClock


@dataclass
class Fixture:
    """招待の実UseCaseと保存結果を観測する。"""

    service: IdentityUseCaseSet
    repositories: IdentityRepositories
    clock: FakeClock
    person: AccountPerson
    command: InviteUserCommand


async def _setup() -> Fixture:
    service = create_identity_use_cases()
    person = AccountPerson(
        id=AccountPersonId.generate(),
        names=PersonNames.create(
            last_name="山田",
            first_name="太郎",
            last_name_kana="ヤマダ",
            first_name_kana="タロウ",
        ),
    )
    await service.repositories.people.save(person)
    command = InviteUserCommand(
        corporate_id=str(CorporateId.generate().value),
        person_id=str(person.id.value),
        addressee="person@example.test",
        role=MembershipRole.CORPORATE_ADMIN,
        expires_at=service.clock.now() + timedelta(days=1),
    )
    return Fixture(service, service.repositories, service.clock, person, command)


@pytest.mark.asyncio
@pytest.mark.parametrize("existing_account", [False, True])
async def test_招待は本人の既存アカウントを再利用して一度だけ受諾できる(
    existing_account: bool,
) -> None:
    fixture = await _setup()
    original = UserAccount(id=UserAccountId.generate(), person_id=fixture.person.id)
    if existing_account:
        await fixture.repositories.accounts.save(original)
    issued = await fixture.service.invite.execute(fixture.command)
    from app.domain.identity.primitives import UserInvitationId

    stored = await fixture.repositories.invitations.get(
        UserInvitationId.parse(issued.id)
    )
    assert stored is not None and stored.secret_digest.value != issued.secret
    identity = VerifiedIdentity(
        person_id=fixture.person.id, principal_id="issuer/verified-subject"
    )
    account = await fixture.service.accept.execute(issued.secret, identity)
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
        await fixture.service.accept.execute(issued.secret, identity)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "violation", ["別人", "期限一致", "期限超過", "取消", "秘密不一致"]
)
async def test_無効な招待受諾ではアカウントを作らない(violation: str) -> None:
    fixture = await _setup()
    issued = await fixture.service.invite.execute(fixture.command)
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
        await fixture.service.accept.execute(
            secret,
            VerifiedIdentity(
                person_id=person_id, principal_id="issuer/verified-subject"
            ),
        )
    assert await fixture.repositories.accounts.get_by_person(fixture.person.id) is None


@pytest.mark.asyncio
async def test_招待を管理者が取り消すと本人も受諾できない() -> None:
    fixture = await _setup()
    issued = await fixture.service.invite.execute(fixture.command)
    await fixture.service.cancel_invitation.execute(
        fixture.command.corporate_id, issued.id
    )
    with pytest.raises(DomainError):
        await fixture.service.accept.execute(
            issued.secret,
            VerifiedIdentity(
                person_id=fixture.person.id, principal_id="issuer/subject"
            ),
        )
