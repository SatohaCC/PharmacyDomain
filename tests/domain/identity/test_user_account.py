"""個人アカウントの本人参照を確認する。"""

from dataclasses import fields
from typing import cast

import pytest

from app.domain.foundation.exceptions import DomainValidationError
from app.domain.identity.primitives import AccountPersonId, AccountStatus, UserAccountId
from app.domain.identity.user_account import UserAccount


def test_本人のないアカウントを構築できない() -> None:
    with pytest.raises(DomainValidationError):
        UserAccount(id=UserAccountId.generate(), person_id=cast(AccountPersonId, None))


def test_アカウントは法人所有を表すフィールドを持たない() -> None:
    assert "person_id" in {item.name for item in fields(UserAccount)}
    assert "corporate_id" not in {item.name for item in fields(UserAccount)}


def test_停止して再開しても_同じ人と同じアカウントである() -> None:
    account = UserAccount(
        id=UserAccountId.generate(), person_id=AccountPersonId.generate()
    )

    suspended = account.suspend()
    resumed = suspended.reactivate()

    assert suspended.status == AccountStatus.SUSPENDED
    assert resumed.status == AccountStatus.ACTIVE
    assert suspended.person_id == resumed.person_id == account.person_id
    assert suspended.id == resumed.id == account.id
