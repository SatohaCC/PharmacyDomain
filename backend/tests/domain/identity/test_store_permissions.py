"""店舗単位の停止が法人権限や他店舗の利用へ波及しないことを検証する。"""

import pytest

from app.domain.corporate.identifiers import CorporateId
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.identity.entities import CorporateMembership
from app.domain.identity.identifiers import CorporateMembershipId
from app.domain.identity.primitives import MembershipRole
from app.domain.shared.actor import UserAccountId
from app.domain.store.identifiers import StoreId


def _membership() -> CorporateMembership:
    return CorporateMembership(
        id=CorporateMembershipId.generate(),
        account_id=UserAccountId.generate(),
        corporate_id=CorporateId.generate(),
        role=MembershipRole.CORPORATE_ADMIN,
        store_ids=frozenset({StoreId.generate(), StoreId.generate()}),
    )


def test_店舗権限_法人管理者の一店舗を停止しても_他店舗と法人権限は維持する() -> None:
    # Arrange
    membership = _membership()
    store = next(iter(membership.store_ids))
    # Act
    updated = membership.change_store_access(store_id=store, is_active=False)
    # Assert
    assert updated.role == MembershipRole.CORPORATE_ADMIN
    assert updated.store_ids == membership.store_ids
    assert updated.active_store_ids == membership.store_ids - {store}
    assert membership.active_store_ids == membership.store_ids


def test_店舗権限_停止した店舗を再開すると_元の範囲に戻る() -> None:
    # Arrange
    membership = _membership()
    store = next(iter(membership.store_ids))
    stopped = membership.change_store_access(store_id=store, is_active=False)
    # Act
    updated = stopped.change_store_access(store_id=store, is_active=True)
    # Assert
    assert updated.active_store_ids == membership.store_ids


def test_店舗権限_未所属店舗の利用状態を変更すると_拒否する() -> None:
    # Arrange
    membership = _membership()
    # Act / Assert
    with pytest.raises(DomainValidationError):
        membership.change_store_access(store_id=StoreId.generate(), is_active=False)
