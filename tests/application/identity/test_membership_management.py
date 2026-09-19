"""最後の管理者保護を実際のアカウント・所属更新へ適用する。"""

from dataclasses import replace

import pytest

from app.domain.corporate.primitives import CorporateId
from app.domain.identity.exceptions import IdentityConflictError
from app.domain.identity.membership import CorporateMembership
from app.domain.identity.primitives import (
    AccountPersonId,
    AccountStatus,
    CorporateMembershipId,
    MembershipRole,
    UserAccountId,
)
from app.domain.identity.user_account import UserAccount
from tests.application.identity.test_invitation_management import _setup


@pytest.mark.asyncio
@pytest.mark.parametrize("whole_account", [True, False])
@pytest.mark.parametrize("other_admin", [True, False])
async def test_実効的な最後の管理者を停止すると保存されない(
    whole_account: bool, other_admin: bool
) -> None:
    fixture = await _setup()
    account = UserAccount(id=UserAccountId.generate(), person_id=fixture.person.id)
    corporate_id = CorporateId.parse(fixture.command.corporate_id)
    membership = CorporateMembership(
        id=CorporateMembershipId.generate(),
        corporate_id=corporate_id,
        account_id=account.id,
        role=MembershipRole.CORPORATE_ADMIN,
        store_ids=frozenset(),
    )
    await fixture.repositories.accounts.save(account)
    await fixture.repositories.memberships.save(membership)
    if other_admin:
        other_person = replace(fixture.person, id=AccountPersonId.generate())
        await fixture.repositories.people.save(other_person)
        other_account = replace(
            account, id=UserAccountId.generate(), person_id=other_person.id
        )
        await fixture.repositories.accounts.save(other_account)
        await fixture.repositories.memberships.save(
            replace(
                membership,
                id=CorporateMembershipId.generate(),
                account_id=other_account.id,
            )
        )

    async def change() -> None:
        if whole_account:
            await fixture.service.suspend_account.execute(str(account.id.value))
        else:
            await fixture.service.change_membership.execute(
                str(corporate_id.value),
                str(membership.id.value),
                status=AccountStatus.SUSPENDED,
            )

    if other_admin:
        await change()
    else:
        with pytest.raises(IdentityConflictError):
            await change()
    actual_account = await fixture.repositories.accounts.get(account.id)
    actual_membership = await fixture.repositories.memberships.get(membership.id)
    assert actual_account is not None and actual_membership is not None
    assert actual_account.person_id == fixture.person.id
    assert actual_account.status == (
        AccountStatus.SUSPENDED
        if other_admin and whole_account
        else AccountStatus.ACTIVE
    )
    assert actual_membership.status == (
        AccountStatus.SUSPENDED
        if other_admin and not whole_account
        else AccountStatus.ACTIVE
    )
