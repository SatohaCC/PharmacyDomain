"""店舗状態と不変な変更履歴の契約。"""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app.domain.foundation.exceptions import DomainError, DomainValidationError
from app.domain.identity.primitives import AccountPersonId, UserAccountId
from app.domain.store.lifecycle import StoreStatus, StoreStatusReason
from app.domain.store.store import Store
from tests.factories.store_factory import create_store

_NOW = datetime(2026, 9, 17, 2, tzinfo=UTC)
_PERSON = AccountPersonId.generate()
_ACCOUNT = UserAccountId.generate()


def _change(store: Store, status: StoreStatus) -> Store:
    return store.change_status(
        status,
        reason=StoreStatusReason("管理者による変更"),
        person_id=_PERSON,
        account_id=_ACCOUNT,
        recorded_at=_NOW,
    )


def test_新規店舗は稼働状態で履歴が空である() -> None:
    store = create_store()
    assert store.status == StoreStatus.ACTIVE
    assert store.status_history == ()


@pytest.mark.parametrize(
    ("before", "after"),
    [
        (StoreStatus.ACTIVE, StoreStatus.SUSPENDED),
        (StoreStatus.SUSPENDED, StoreStatus.ACTIVE),
        (StoreStatus.ACTIVE, StoreStatus.CLOSED),
        (StoreStatus.SUSPENDED, StoreStatus.CLOSED),
    ],
)
def test_許可された状態変更は_元の店舗を変更せず履歴を残す(
    before: StoreStatus, after: StoreStatus
) -> None:
    store = replace(create_store(), status=before)

    updated = _change(store, after)

    assert store.status == before
    assert store.status_history == ()
    assert updated.status == after
    assert len(updated.status_history) == 1
    change = updated.status_history[0]
    assert (change.before, change.after) == (before, after)
    assert change.person_id == _PERSON
    assert change.account_id == _ACCOUNT
    assert change.recorded_at == _NOW


@pytest.mark.parametrize("target", [StoreStatus.ACTIVE, StoreStatus.SUSPENDED])
def test_閉局店舗は再開や休止へ戻せない(target: StoreStatus) -> None:
    store = replace(create_store(), status=StoreStatus.CLOSED)
    with pytest.raises(DomainError):
        _change(store, target)


@pytest.mark.parametrize("target", list(StoreStatus))
def test_同じ状態への再送で履歴を増やさない(target: StoreStatus) -> None:
    source = (
        StoreStatus.SUSPENDED if target == StoreStatus.ACTIVE else StoreStatus.ACTIVE
    )
    store = _change(replace(create_store(), status=source), target)

    again = _change(store, target)

    assert again.status == store.status
    assert again.status_history == store.status_history


def test_タイムゾーンの無い記録日時は拒否される() -> None:
    naive_now = datetime(2026, 9, 17, 2)  # noqa: DTZ001
    store = create_store()
    with pytest.raises(
        DomainValidationError, match="記録日時にはタイムゾーンが必要です"
    ):
        store.change_status(
            StoreStatus.SUSPENDED,
            reason=StoreStatusReason("管理者による変更"),
            person_id=_PERSON,
            account_id=_ACCOUNT,
            recorded_at=naive_now,
        )
