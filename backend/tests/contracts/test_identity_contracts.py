"""個人アカウントと法人アクセス権の保存契約。"""

from dataclasses import replace

import pytest

from app.domain.corporate.identifiers import CorporateId
from app.domain.identity.entities import CorporateMembership, UserAccount
from app.domain.identity.exceptions import IdentityConflictError
from app.domain.identity.identifiers import CorporateMembershipId
from app.domain.identity.primitives import (
    AccountStatus,
    ExternalSubjectKey,
    MembershipRole,
)
from app.domain.shared.actor import AccountPersonId, UserAccountId
from app.domain.staff.identifiers import StaffId
from tests.fakes.in_memory_identity_repositories import (
    InMemoryCorporateMembershipRepository,
    InMemoryUserAccountRepository,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", list(AccountStatus))
async def test_同じ人へ二つ目のアカウントを作れない(status: AccountStatus) -> None:
    repository = InMemoryUserAccountRepository()
    corporate_id = CorporateId.generate()
    original = UserAccount(
        id=UserAccountId.generate(),
        corporate_id=corporate_id,
        person_id=AccountPersonId.generate(),
        status=status,
    )
    await repository.save(original)

    with pytest.raises(IdentityConflictError):
        await repository.save(replace(original, id=UserAccountId.generate()))
    assert (
        await repository.get_by_person(original.corporate_id, original.person_id)
        == original
    )


@pytest.mark.asyncio
async def test_保存済みアカウントを別人へ付け替えられない() -> None:
    repository = InMemoryUserAccountRepository()
    corporate_id = CorporateId.generate()
    original = UserAccount(
        id=UserAccountId.generate(),
        corporate_id=corporate_id,
        person_id=AccountPersonId.generate(),
    )
    await repository.save(original)

    with pytest.raises(IdentityConflictError):
        await repository.save(replace(original, person_id=AccountPersonId.generate()))
    actual = await repository.get(original.id)
    assert actual is not None
    assert actual.person_id == original.person_id


def _membership() -> CorporateMembership:
    return CorporateMembership(
        id=CorporateMembershipId.generate(),
        account_id=UserAccountId.generate(),
        corporate_id=CorporateId.generate(),
        role=MembershipRole.CORPORATE_ADMIN,
        store_ids=frozenset(),
        staff_id=StaffId.generate(),
    )


@pytest.mark.asyncio
async def test_同時に有効な法人アクセス権は一つに限る() -> None:
    repository = InMemoryCorporateMembershipRepository()
    original = _membership()
    await repository.save(original)

    with pytest.raises(IdentityConflictError):
        await repository.save(
            replace(
                original,
                id=CorporateMembershipId.generate(),
                corporate_id=CorporateId.generate(),
                staff_id=None,
            )
        )
    assert await repository.find_active_for_account(original.account_id) == original


@pytest.mark.asyncio
async def test_旧法人のアクセス停止後は同じアカウントで別法人へ所属できる() -> None:
    repository = InMemoryCorporateMembershipRepository()
    original = replace(_membership(), status=AccountStatus.SUSPENDED)
    await repository.save(original)
    new = replace(
        original,
        id=CorporateMembershipId.generate(),
        corporate_id=CorporateId.generate(),
        staff_id=None,
        status=AccountStatus.ACTIVE,
    )

    await repository.save(new)

    assert await repository.get(original.id) == original
    assert await repository.find_active_for_account(original.account_id) == new


@pytest.mark.asyncio
async def test_同じスタッフを別アカウントへ紐付けられない() -> None:
    repository = InMemoryCorporateMembershipRepository()
    original = _membership()
    await repository.save(original)
    with pytest.raises(IdentityConflictError):
        await repository.save(
            replace(
                original,
                id=CorporateMembershipId.generate(),
                account_id=UserAccountId.generate(),
            )
        )


@pytest.mark.asyncio
async def test_同じ外部主体を別の人に割り当てられない() -> None:
    repository = InMemoryUserAccountRepository()
    corporate_id = CorporateId.generate()
    original = UserAccount(
        id=UserAccountId.generate(),
        corporate_id=corporate_id,
        person_id=AccountPersonId.generate(),
        external_subject=ExternalSubjectKey("issuer/subject"),
    )
    await repository.save(original)
    with pytest.raises(IdentityConflictError):
        await repository.save(
            replace(
                original,
                id=UserAccountId.generate(),
                person_id=AccountPersonId.generate(),
            )
        )
    assert (
        await repository.get_by_subject(ExternalSubjectKey("issuer/subject"))
        == original
    )


@pytest.mark.asyncio
async def test_外部主体を固定していないアカウントは主体では引けない() -> None:
    """未固定のアカウントは、どの主体からも到達できない。

    ``ResolveActorUseCase`` は外部主体からアカウントを引く。ここで未固定の行が
    返る実装があると、照合が「そのアカウントだけ効かない」形に戻る。分岐では
    なく検索の契約として全実装へ課す。
    """
    # Arrange
    repository = InMemoryUserAccountRepository()
    corporate_id = CorporateId.generate()
    await repository.save(
        UserAccount(
            id=UserAccountId.generate(),
            corporate_id=corporate_id,
            person_id=AccountPersonId.generate(),
        )
    )

    # Act & Assert
    assert await repository.get_by_subject(ExternalSubjectKey("issuer/subject")) is None


@pytest.mark.asyncio
async def test_TC025_同法人の明示選択済み本人へ2件目のアカウント作成を拒否する() -> (
    None
):
    """同一法人の同一本人に対して2つ目のアカウントは作成できない。"""
    repository = InMemoryUserAccountRepository()
    corporate_id = CorporateId.generate()
    person_id = AccountPersonId.generate()
    account1 = UserAccount(
        id=UserAccountId.generate(),
        corporate_id=corporate_id,
        person_id=person_id,
    )
    await repository.save(account1)

    account2 = UserAccount(
        id=UserAccountId.generate(),
        corporate_id=corporate_id,
        person_id=person_id,
    )
    with pytest.raises(IdentityConflictError):
        await repository.save(account2)


@pytest.mark.asyncio
async def test_TC036_別法人であれば同本人や同外部主体のアカウントが独立して保存できる() -> (
    None
):
    """別法人であれば法人横断の一意制約に阻まれず独立して保存できる。"""
    repository = InMemoryUserAccountRepository()
    corp_a = CorporateId.generate()
    corp_b = CorporateId.generate()
    person_id = AccountPersonId.generate()
    subject = ExternalSubjectKey("issuer/same_subject")

    account_a = UserAccount(
        id=UserAccountId.generate(),
        corporate_id=corp_a,
        person_id=person_id,
        external_subject=subject,
    )
    account_b = UserAccount(
        id=UserAccountId.generate(),
        corporate_id=corp_b,
        person_id=person_id,
        external_subject=subject,
    )
    await repository.save(account_a)
    await repository.save(account_b)

    assert await repository.find_for_corporate(corp_a, account_a.id) == account_a
    assert await repository.find_for_corporate(corp_b, account_b.id) == account_b
    assert await repository.get_by_person(corp_a, person_id) == account_a
    assert await repository.get_by_person(corp_b, person_id) == account_b
