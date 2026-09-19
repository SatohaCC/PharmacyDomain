"""本人指定・期限・単回利用を含む招待の発行と、外部主体による受諾。"""

from dataclasses import dataclass, replace
from datetime import timedelta

import pytest

from app.application.identity.invite_user import InviteUserCommand
from app.application.identity.resolve_actor import VerifiedSubject
from app.application.identity.support import IdentityRepositories
from app.domain.corporate.primitives import CorporateId
from app.domain.foundation.exceptions import DomainError
from app.domain.identity.account_person import AccountPerson
from app.domain.identity.exceptions import IdentityConflictError
from app.domain.identity.invitation import InvitationStatus
from app.domain.identity.primitives import (
    AccountPersonId,
    AccountStatus,
    ExternalSubjectKey,
    MembershipRole,
    UserAccountId,
    UserInvitationId,
)
from app.domain.identity.user_account import UserAccount
from app.domain.shared.person_name import PersonNames
from tests.application.identity.helpers import (
    IdentityUseCaseSet,
    create_identity_use_cases,
)
from tests.fakes.fake_clock import FakeClock

_PRINCIPAL_ID = "issuer/verified-subject"
_SUBJECT = VerifiedSubject(principal_id=_PRINCIPAL_ID)


@dataclass
class Fixture:
    """招待の実UseCaseと保存結果を観測する。"""

    service: IdentityUseCaseSet
    repositories: IdentityRepositories
    clock: FakeClock
    person: AccountPerson
    command: InviteUserCommand


def _person(last_name: str = "山田") -> AccountPerson:
    return AccountPerson(
        id=AccountPersonId.generate(),
        names=PersonNames.create(
            last_name=last_name,
            first_name="太郎",
            last_name_kana="ヤマダ",
            first_name_kana="タロウ",
        ),
    )


async def _setup() -> Fixture:
    service = create_identity_use_cases()
    person = _person()
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
    stored = await fixture.repositories.invitations.get(
        UserInvitationId.parse(issued.id)
    )
    assert stored is not None and stored.secret_digest.value != issued.secret

    account = await fixture.service.accept.execute(issued.secret, _SUBJECT)

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
        await fixture.service.accept.execute(issued.secret, _SUBJECT)


@pytest.mark.asyncio
async def test_受諾は招待の本人に提示された外部主体を固定する() -> None:
    """本人は招待から、外部主体は提示から取る。

    外部の認証基盤は自分が発行した主体しか知らないので、受諾者が名乗る本人IDを
    受け取る形にはできない。本人を招待側に固定しておくことで、秘密を持っている
    ことが「その招待の本人として受諾できる」ことと同じ意味になる。
    """
    fixture = await _setup()
    issued = await fixture.service.invite.execute(fixture.command)

    await fixture.service.accept.execute(issued.secret, _SUBJECT)

    saved = await fixture.repositories.accounts.get_by_person(fixture.person.id)
    assert saved is not None
    assert saved.person_id == fixture.person.id
    assert saved.external_subject == ExternalSubjectKey(_PRINCIPAL_ID)


@pytest.mark.asyncio
@pytest.mark.parametrize("violation", ["期限一致", "期限超過", "取消", "秘密不一致"])
async def test_無効な招待受諾ではアカウントを作らない(violation: str) -> None:
    fixture = await _setup()
    issued = await fixture.service.invite.execute(fixture.command)
    if violation.startswith("期限"):
        fixture.clock.advance(
            timedelta(days=1, seconds=1 if violation == "期限超過" else 0)
        )
    if violation == "取消":
        stored = await fixture.repositories.invitations.get(
            UserInvitationId.parse(issued.id)
        )
        assert stored is not None
        await fixture.repositories.invitations.save(
            replace(stored, status=InvitationStatus.CANCELLED)
        )
    secret = "不正秘密" if violation == "秘密不一致" else issued.secret

    with pytest.raises(DomainError):
        await fixture.service.accept.execute(secret, _SUBJECT)

    assert await fixture.repositories.accounts.get_by_person(fixture.person.id) is None


@pytest.mark.asyncio
async def test_他人に固定済みの外部主体では受諾できない() -> None:
    """提示された主体が既に別の本人のものなら、招待の秘密だけでは通さない。

    本人の照合が招待側へ移った代わりに、ここが「なりすましたアカウントを作れ
    ない」ことを担保する。片方の本人がもう片方の権限を得る経路を塞ぐ。
    """
    fixture = await _setup()
    other = _person("佐藤")
    await fixture.repositories.people.save(other)
    await fixture.repositories.accounts.save(
        UserAccount(
            id=UserAccountId.generate(),
            person_id=other.id,
            external_subject=ExternalSubjectKey(_PRINCIPAL_ID),
        )
    )
    issued = await fixture.service.invite.execute(fixture.command)

    with pytest.raises(IdentityConflictError):
        await fixture.service.accept.execute(issued.secret, _SUBJECT)

    assert await fixture.repositories.accounts.get_by_person(fixture.person.id) is None


@pytest.mark.asyncio
async def test_別の外部主体で固定済みの本人のアカウントは奪えない() -> None:
    """既に別のIdP主体で使われているアカウントを、招待で付け替えさせない。"""
    fixture = await _setup()
    existing = UserAccount(
        id=UserAccountId.generate(),
        person_id=fixture.person.id,
        external_subject=ExternalSubjectKey("issuer/別の主体"),
    )
    await fixture.repositories.accounts.save(existing)
    issued = await fixture.service.invite.execute(fixture.command)

    with pytest.raises(IdentityConflictError):
        await fixture.service.accept.execute(issued.secret, _SUBJECT)

    saved = await fixture.repositories.accounts.get(existing.id)
    assert saved is not None
    assert saved.external_subject == ExternalSubjectKey("issuer/別の主体")


@pytest.mark.asyncio
async def test_停止中のアカウントでは招待を受諾できない() -> None:
    fixture = await _setup()
    await fixture.repositories.accounts.save(
        UserAccount(
            id=UserAccountId.generate(),
            person_id=fixture.person.id,
            status=AccountStatus.SUSPENDED,
        )
    )
    issued = await fixture.service.invite.execute(fixture.command)

    with pytest.raises(IdentityConflictError):
        await fixture.service.accept.execute(issued.secret, _SUBJECT)


@pytest.mark.asyncio
async def test_招待を管理者が取り消すと受諾できない() -> None:
    fixture = await _setup()
    issued = await fixture.service.invite.execute(fixture.command)
    await fixture.service.cancel_invitation.execute(
        fixture.command.corporate_id, issued.id
    )

    with pytest.raises(DomainError):
        await fixture.service.accept.execute(issued.secret, _SUBJECT)
