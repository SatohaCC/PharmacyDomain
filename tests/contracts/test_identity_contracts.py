"""個人アカウントと法人アクセス権の保存契約。"""

from dataclasses import replace

import pytest

from app.domain.corporate.primitives import CorporateId
from app.domain.identity.exceptions import IdentityConflictError
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
from app.domain.staff.primitives import StaffId
from tests.fakes.in_memory_identity_repositories import (
    InMemoryCorporateMembershipRepository,
    InMemoryUserAccountRepository,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", list(AccountStatus))
async def test_同じ人へ二つ目のアカウントを作れない(status: AccountStatus) -> None:
    repository = InMemoryUserAccountRepository()
    original = UserAccount(
        id=UserAccountId.generate(), person_id=AccountPersonId.generate(), status=status
    )
    await repository.save(original)

    with pytest.raises(IdentityConflictError):
        await repository.save(replace(original, id=UserAccountId.generate()))
    assert await repository.get_by_person(original.person_id) == original


@pytest.mark.asyncio
async def test_保存済みアカウントを別人へ付け替えられない() -> None:
    repository = InMemoryUserAccountRepository()
    original = UserAccount(
        id=UserAccountId.generate(), person_id=AccountPersonId.generate()
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
    original = UserAccount(
        id=UserAccountId.generate(),
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
