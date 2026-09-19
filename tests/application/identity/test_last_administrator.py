"""法人アクセス権とアカウント双方を考慮する管理者保護。"""

from dataclasses import replace

import pytest

from app.domain.corporate.primitives import CorporateId
from app.domain.identity.administrator_service import LastAdministratorService
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
from app.domain.staff.primitives import StaffId


def _administrator(
    corporate_id: CorporateId,
) -> tuple[UserAccount, CorporateMembership]:
    account = UserAccount(
        id=UserAccountId.generate(), person_id=AccountPersonId.generate()
    )
    membership = CorporateMembership(
        id=CorporateMembershipId.generate(),
        account_id=account.id,
        corporate_id=corporate_id,
        role=MembershipRole.CORPORATE_ADMIN,
        store_ids=frozenset(),
        staff_id=StaffId.generate(),
    )
    return account, membership


@pytest.mark.parametrize(
    "operation", ["membership停止", "降格", "account停止", "退職連携"]
)
@pytest.mark.parametrize(
    "other_status", ["不在", "有効", "account停止", "membership停止", "他法人"]
)
def test_最後の実効的な管理者を失う変更だけ拒否する(
    operation: str, other_status: str
) -> None:
    corporate_id = CorporateId.generate()
    account, membership = _administrator(corporate_id)
    accounts = [account]
    memberships = [membership]
    if other_status != "不在":
        other_account, other_membership = _administrator(
            CorporateId.generate() if other_status == "他法人" else corporate_id
        )
        if other_status == "account停止":
            other_account = replace(other_account, status=AccountStatus.SUSPENDED)
        if other_status == "membership停止":
            other_membership = replace(other_membership, status=AccountStatus.SUSPENDED)
        accounts.append(other_account)
        memberships.append(other_membership)

    changed_account = (
        replace(account, status=AccountStatus.SUSPENDED)
        if operation == "account停止"
        else account
    )
    if operation == "降格":
        changed_membership = replace(membership, role=MembershipRole.STORE_VIEWER)
    elif operation in {"membership停止", "退職連携"}:
        changed_membership = replace(membership, status=AccountStatus.SUSPENDED)
    else:
        changed_membership = membership

    def check() -> None:
        LastAdministratorService().ensure_preserved(
            corporate_id=corporate_id,
            previous_accounts=accounts,
            previous_memberships=memberships,
            updated_accounts=[changed_account, *accounts[1:]],
            updated_memberships=[changed_membership, *memberships[1:]],
        )

    if other_status == "有効":
        check()
    else:
        with pytest.raises(IdentityConflictError):
            check()
    assert account.status == AccountStatus.ACTIVE
    assert membership.role == MembershipRole.CORPORATE_ADMIN
    assert membership.status == AccountStatus.ACTIVE


def test_初期状態の管理者不在は最初の管理者作成を妨げない() -> None:
    corporate_id = CorporateId.generate()
    account, membership = _administrator(corporate_id)
    LastAdministratorService().ensure_preserved(
        corporate_id=corporate_id,
        previous_accounts=[],
        previous_memberships=[],
        updated_accounts=[account],
        updated_memberships=[membership],
    )


def test_管理者不在の初期法人では招待発行前の状態を維持できる() -> None:
    LastAdministratorService().ensure_preserved(
        corporate_id=CorporateId.generate(),
        previous_accounts=[],
        previous_memberships=[],
        updated_accounts=[],
        updated_memberships=[],
    )
