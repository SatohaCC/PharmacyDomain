"""外部主体からアカウント・権限を解決し、変更を次の要求へ反映する。"""

from dataclasses import replace

import pytest

from app.application.access_control.models import ActorRole
from app.application.identity.resolve_actor import (
    ResolveActorUseCase,
    UnavailableIdentityError,
    VerifiedSubject,
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

_PRINCIPAL_ID = "issuer/検証済み主体"


async def _setup() -> tuple[
    ResolveActorUseCase,
    VerifiedSubject,
    InMemoryAccountPersonRepository,
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
    # 解決の出発点は外部主体なので、固定済みを既定にする。
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
        VerifiedSubject(principal_id=_PRINCIPAL_ID),
        people,
        accounts,
        memberships,
        account,
        membership,
    )


@pytest.mark.asyncio
async def test_本人とアカウントと法人権限を含む主体を返す() -> None:
    resolver, subject, _, _, _, account, membership = await _setup()

    actor = await resolver.execute(subject)

    assert actor.principal_id == _PRINCIPAL_ID
    assert actor.person_id == account.person_id
    assert actor.account_id == account.id
    assert actor.membership_id == membership.id
    assert actor.corporate_id == membership.corporate_id
    assert actor.store_ids == membership.store_ids
    assert actor.roles == frozenset({ActorRole.STORE_OPERATOR})


@pytest.mark.asyncio
async def test_個人アカウント停止を同じ主体の次要求へ反映する() -> None:
    resolver, subject, _, accounts, _, account, _ = await _setup()
    await resolver.execute(subject)
    await accounts.save(replace(account, status=AccountStatus.SUSPENDED))

    with pytest.raises(UnavailableIdentityError):
        await resolver.execute(subject)


@pytest.mark.asyncio
async def test_法人アクセス停止を同じ主体の次要求へ反映する() -> None:
    resolver, subject, _, _, memberships, _, membership = await _setup()
    await resolver.execute(subject)
    await memberships.save(replace(membership, status=AccountStatus.SUSPENDED))

    with pytest.raises(UnavailableIdentityError):
        await resolver.execute(subject)


@pytest.mark.asyncio
async def test_権限変更後は古い店舗集合を使わない() -> None:
    resolver, subject, _, _, memberships, _, membership = await _setup()
    before = await resolver.execute(subject)
    new_stores = frozenset({StoreId.generate()})
    await memberships.save(
        replace(membership, role=MembershipRole.STORE_VIEWER, store_ids=new_stores)
    )

    after = await resolver.execute(subject)

    assert after.person_id == before.person_id
    assert after.account_id == before.account_id
    assert after.roles == frozenset({ActorRole.STORE_VIEWER})
    assert after.store_ids == new_stores
    assert not after.store_ids.intersection(before.store_ids)


@pytest.mark.asyncio
async def test_ベンダーも本人とアカウントを持ち法人所属を要求しない() -> None:
    resolver, subject, _, accounts, memberships, account, membership = await _setup()
    await accounts.save(replace(account, is_vendor_admin=True))
    await memberships.save(replace(membership, status=AccountStatus.SUSPENDED))

    actor = await resolver.execute(subject)

    assert actor.person_id == account.person_id
    assert actor.account_id == account.id
    assert actor.corporate_id is None
    assert actor.roles == frozenset({ActorRole.VENDOR_SYSTEM_ADMIN})


@pytest.mark.asyncio
async def test_未知の外部主体を操作主体として通さない() -> None:
    """どのアカウントにも固定されていない主体は解決しない。

    外部主体で引く形にしたので、「別の主体を名乗る」ことと「その主体が存在
    しない」ことが同じ事象になる。本人IDを外から受け取っていた頃は、本人が
    一致しさえすれば任意の主体で権限を発行できる余地が型の上に残っていた。
    """
    resolver, _, _, _, _, _, _ = await _setup()

    with pytest.raises(UnavailableIdentityError):
        await resolver.execute(VerifiedSubject(principal_id="issuer/未知の主体"))


@pytest.mark.asyncio
async def test_外部主体を固定していないアカウントは解決しない() -> None:
    """未固定のアカウントは、どの主体からも到達できない。

    照合を分岐で書いていた頃は「外部主体が空なら照合を飛ばす」と書けてしまい、
    第二の防衛線がまさに主体を固定していないアカウントにだけ効かなくなっていた。
    主体で引く形にすると、この経路は分岐ではなく検索の結果として消える。
    """
    resolver, subject, _, accounts, _, account, _ = await _setup()
    await accounts.save(replace(account, external_subject=None))

    with pytest.raises(UnavailableIdentityError):
        await resolver.execute(subject)


@pytest.mark.asyncio
async def test_本人の行が無いアカウントは操作主体にならない() -> None:
    """アカウントから本人へたどる順序になったので、この抜けが到達可能になる。

    本人を先に引いていた頃は、本人が居ないことが最初に分かった。アカウントを
    先に引く形では、本人の行が消えていても権限だけで主体を組み立てられてしまう。
    監査の追記は本人とアカウントの両方を要求するので、ここで止める。
    """
    resolver, subject, people, _, _, account, _ = await _setup()
    people.items.pop(account.person_id)

    with pytest.raises(UnavailableIdentityError):
        await resolver.execute(subject)
