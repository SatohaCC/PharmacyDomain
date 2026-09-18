"""アカウント・権限の変更を次の要求へ反映する。"""

from dataclasses import replace

import pytest

from app.application.access_control import ActorRole
from app.application.identity.resolve_actor import (
    ResolveActorUseCase,
    UnavailableIdentityError,
    VerifiedIdentity,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.identity.account_person import AccountPerson
from app.domain.identity.membership import CorporateMembership
from app.domain.identity.primitives import (
    AccountPersonId,
    AccountStatus,
    CorporateMembershipId,
    ExternalSubjectKey,
    MembershipRole,
    UserAccountId,
)
from app.domain.identity.user_account import UserAccount
from app.domain.shared.person_name import PersonNames
from app.domain.staff.primitives import StaffId
from app.domain.store.primitives import StoreId
from tests.fakes.in_memory_identity_repositories import (
    InMemoryAccountPersonRepository,
    InMemoryCorporateMembershipRepository,
    InMemoryUserAccountRepository,
)

_PRINCIPAL_ID = "issuer/検証済み本人"


async def _setup() -> tuple[
    ResolveActorUseCase,
    VerifiedIdentity,
    InMemoryUserAccountRepository,
    InMemoryCorporateMembershipRepository,
    UserAccount,
    CorporateMembership,
]:
    people = InMemoryAccountPersonRepository()
    accounts = InMemoryUserAccountRepository()
    memberships = InMemoryCorporateMembershipRepository()
    person = AccountPerson(
        id=AccountPersonId.generate(),
        names=PersonNames.create(
            last_name="山田",
            first_name="太郎",
            last_name_kana="ヤマダ",
            first_name_kana="タロウ",
        ),
    )
    # 外部主体を固定していないアカウントは解決しない。固定済みを既定にする。
    account = UserAccount(
        id=UserAccountId.generate(),
        person_id=person.id,
        external_subject=ExternalSubjectKey(_PRINCIPAL_ID),
    )
    membership = CorporateMembership(
        id=CorporateMembershipId.generate(),
        account_id=account.id,
        corporate_id=CorporateId.generate(),
        role=MembershipRole.STORE_OPERATOR,
        store_ids=frozenset({StoreId.generate()}),
        staff_id=StaffId.generate(),
    )
    await people.save(person)
    await accounts.save(account)
    await memberships.save(membership)
    return (
        ResolveActorUseCase(people, accounts, memberships),
        VerifiedIdentity(person_id=person.id, principal_id=_PRINCIPAL_ID),
        accounts,
        memberships,
        account,
        membership,
    )


@pytest.mark.asyncio
async def test_本人とアカウントと法人権限を含む主体を返す() -> None:
    resolver, identity, _, _, account, membership = await _setup()

    actor = await resolver.execute(identity)

    assert actor.person_id == account.person_id
    assert actor.account_id == account.id
    assert actor.membership_id == membership.id
    assert actor.corporate_id == membership.corporate_id
    assert actor.store_ids == membership.store_ids
    assert actor.roles == frozenset({ActorRole.STORE_OPERATOR})


@pytest.mark.asyncio
async def test_個人アカウント停止を同じ本人の次要求へ反映する() -> None:
    resolver, identity, accounts, _, account, _ = await _setup()
    await resolver.execute(identity)
    await accounts.save(replace(account, status=AccountStatus.SUSPENDED))

    with pytest.raises(UnavailableIdentityError):
        await resolver.execute(identity)


@pytest.mark.asyncio
async def test_法人アクセス停止を同じ本人の次要求へ反映する() -> None:
    resolver, identity, _, memberships, _, membership = await _setup()
    await resolver.execute(identity)
    await memberships.save(replace(membership, status=AccountStatus.SUSPENDED))

    with pytest.raises(UnavailableIdentityError):
        await resolver.execute(identity)


@pytest.mark.asyncio
async def test_権限変更後は古い店舗集合を使わない() -> None:
    resolver, identity, _, memberships, _, membership = await _setup()
    before = await resolver.execute(identity)
    new_stores = frozenset({StoreId.generate()})
    await memberships.save(
        replace(membership, role=MembershipRole.STORE_VIEWER, store_ids=new_stores)
    )

    after = await resolver.execute(identity)

    assert after.person_id == before.person_id
    assert after.account_id == before.account_id
    assert after.roles == frozenset({ActorRole.STORE_VIEWER})
    assert after.store_ids == new_stores
    assert not after.store_ids.intersection(before.store_ids)


@pytest.mark.asyncio
async def test_未登録の本人を操作主体として通さない() -> None:
    resolver, _, _, _, _, _ = await _setup()
    with pytest.raises(UnavailableIdentityError):
        await resolver.execute(
            VerifiedIdentity(
                person_id=AccountPersonId.generate(), principal_id="未知の本人"
            )
        )


@pytest.mark.asyncio
async def test_ベンダーも本人とアカウントを持ち法人所属を要求しない() -> None:
    resolver, identity, accounts, memberships, account, membership = await _setup()
    await accounts.save(replace(account, is_vendor_admin=True))
    await memberships.save(replace(membership, status=AccountStatus.SUSPENDED))
    actor = await resolver.execute(identity)
    assert actor.person_id == identity.person_id
    assert actor.account_id == account.id
    assert actor.corporate_id is None
    assert actor.roles == frozenset({ActorRole.VENDOR_SYSTEM_ADMIN})


@pytest.mark.asyncio
async def test_同じ本人を名乗っても保存済み外部主体と異なる場合は拒否する() -> None:
    resolver, identity, accounts, _, account, _ = await _setup()
    await accounts.save(
        replace(account, external_subject=ExternalSubjectKey("issuer/original"))
    )
    with pytest.raises(UnavailableIdentityError):
        await resolver.execute(identity)


@pytest.mark.asyncio
async def test_外部主体を固定していないアカウントは解決しない() -> None:
    """照合が「そのアカウントだけ効かない」形になるのを防ぐ。

    ``external_subject`` が空のとき照合を飛ばすと、本人IDさえ一致すれば任意の
    principal_id でそのアカウントの権限（ベンダー権限を含む）を発行できる。
    第二の防衛線が、まさに主体を固定していないアカウントにだけ効かなくなる。
    """
    # Arrange
    resolver, identity, accounts, _, account, _ = await _setup()
    await accounts.save(replace(account, external_subject=None))

    # Act & Assert
    with pytest.raises(UnavailableIdentityError):
        await resolver.execute(identity)
