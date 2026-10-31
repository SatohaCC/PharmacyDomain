"""個人アカウントの本人参照および法人帰属を確認する（TC-023）。"""

from dataclasses import fields
from typing import cast

import pytest

from app.domain.corporate.identifiers import CorporateId
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.identity.entities import UserAccount
from app.domain.identity.primitives import AccountStatus
from app.domain.shared.actor import AccountPersonId, UserAccountId


def test_本人のないアカウントを構築できない() -> None:
    with pytest.raises(DomainValidationError):
        UserAccount(
            id=UserAccountId.generate(),
            corporate_id=CorporateId.generate(),
            person_id=cast(AccountPersonId, None),
        )


def test_TC023_アカウントは法人所有を表すフィールドを持つ() -> None:
    field_names = {item.name for item in fields(UserAccount)}
    assert "person_id" in field_names
    assert "corporate_id" in field_names


def test_停止して再開しても_同じ人と同じアカウントである() -> None:
    corporate_id = CorporateId.generate()
    account = UserAccount(
        id=UserAccountId.generate(),
        corporate_id=corporate_id,
        person_id=AccountPersonId.generate(),
    )

    suspended = account.suspend()
    resumed = suspended.reactivate()

    assert suspended.status == AccountStatus.SUSPENDED
    assert resumed.status == AccountStatus.ACTIVE
    assert suspended.person_id == resumed.person_id == account.person_id
    assert suspended.corporate_id == resumed.corporate_id == corporate_id
    assert suspended.id == resumed.id == account.id
