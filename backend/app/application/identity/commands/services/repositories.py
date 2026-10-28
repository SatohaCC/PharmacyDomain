"""Applicationのsupportを定義する。"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.identity.repositories import (
    AccountPersonRepository,
    CorporateMembershipRepository,
    StaffPersonLinkRepository,
    UserAccountRepository,
    UserInvitationRepository,
)


@dataclass(frozen=True)
class IdentityRepositories:
    """同じUoWに接続されたIdentityの保存境界。"""

    people: AccountPersonRepository
    accounts: UserAccountRepository
    memberships: CorporateMembershipRepository
    links: StaffPersonLinkRepository
    invitations: UserInvitationRepository
