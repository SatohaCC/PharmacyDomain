"""本人指定と期限境界を持つ招待のテスト。"""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from app.domain.corporate.primitives import CorporateId
from app.domain.foundation.exceptions import DomainError
from app.domain.identity.invitation import (
    InvitationDigest,
    InvitationStatus,
    UserInvitation,
)
from app.domain.identity.primitives import (
    AccountPersonId,
    MembershipRole,
    UserInvitationId,
)

_EXPIRY = datetime(2026, 9, 18, 0, tzinfo=UTC)


def _invitation() -> UserInvitation:
    return UserInvitation(
        id=UserInvitationId.generate(),
        person_id=AccountPersonId.generate(),
        corporate_id=CorporateId.generate(),
        role=MembershipRole.CORPORATE_ADMIN,
        store_ids=frozenset(),
        secret_digest=InvitationDigest("a" * 64),
        expires_at=_EXPIRY,
    )


def test_期限直前に本人が受諾できる() -> None:
    invitation = _invitation()
    accepted = invitation.accept(
        person_id=invitation.person_id, now=_EXPIRY - timedelta(microseconds=1)
    )
    assert accepted.status == InvitationStatus.ACCEPTED
    assert accepted.person_id == invitation.person_id
    assert invitation.status == InvitationStatus.PENDING


@pytest.mark.parametrize("delta", [timedelta(), timedelta(microseconds=1)])
def test_期限時刻以降は受諾できない(delta: timedelta) -> None:
    invitation = _invitation()
    with pytest.raises(DomainError):
        invitation.accept(person_id=invitation.person_id, now=_EXPIRY + delta)


def test_別の人は期限内でも受諾できない() -> None:
    invitation = _invitation()
    with pytest.raises(DomainError):
        invitation.accept(
            person_id=AccountPersonId.generate(), now=_EXPIRY - timedelta(hours=1)
        )


@pytest.mark.parametrize(
    "status", [InvitationStatus.ACCEPTED, InvitationStatus.CANCELLED]
)
def test_使用済みや取消済みの招待は再利用できない(status: InvitationStatus) -> None:
    invitation = replace(_invitation(), status=status)
    with pytest.raises(DomainError):
        invitation.accept(
            person_id=invitation.person_id, now=_EXPIRY - timedelta(hours=1)
        )


def test_招待を取り消しても本人と予定権限を保持する() -> None:
    invitation = _invitation()
    cancelled = invitation.cancel()
    assert cancelled.status == InvitationStatus.CANCELLED
    assert cancelled.person_id == invitation.person_id
    assert cancelled.role == invitation.role
    assert cancelled.corporate_id == invitation.corporate_id
