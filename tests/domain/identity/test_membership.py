"""法人アクセス権と個人アカウントの分離。"""

import pytest

from app.domain.corporate.primitives import CorporateId
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.identity.membership import CorporateMembership
from app.domain.identity.primitives import (
    AccountStatus,
    CorporateMembershipId,
    MembershipRole,
    UserAccountId,
)
from app.domain.store.primitives import StoreId


def _membership(role: MembershipRole) -> CorporateMembership:
    return CorporateMembership(
        id=CorporateMembershipId.generate(),
        account_id=UserAccountId.generate(),
        corporate_id=CorporateId.generate(),
        role=role,
        store_ids=frozenset(),
    )


@pytest.mark.parametrize(
    "role", [MembershipRole.STORE_OPERATOR, MembershipRole.STORE_VIEWER]
)
def test_店舗ロールにはスタッフへの参照が必須である(role: MembershipRole) -> None:
    with pytest.raises(DomainValidationError):
        _membership(role)


def test_法人管理者のアクセス権はスタッフ参照がなくても作れる() -> None:
    membership = _membership(MembershipRole.CORPORATE_ADMIN)
    assert membership.staff_id is None
    assert membership.account_id is not None


def test_法人アクセスの停止は本人のアカウント参照を維持する() -> None:
    original = _membership(MembershipRole.CORPORATE_ADMIN)

    stopped = original.suspend()

    assert stopped.status == AccountStatus.SUSPENDED
    assert stopped.account_id == original.account_id
    assert stopped.corporate_id == original.corporate_id
    assert original.status == AccountStatus.ACTIVE


def test_権限変更は法人とアカウントの対応を変更しない() -> None:
    original = _membership(MembershipRole.CORPORATE_ADMIN)
    stores = frozenset({StoreId.generate()})

    changed = original.change_access(
        role=MembershipRole.CORPORATE_ADMIN, store_ids=stores
    )

    assert changed.account_id == original.account_id
    assert changed.corporate_id == original.corporate_id
    assert changed.store_ids == stores
