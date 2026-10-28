"""Applicationのdtoを定義する。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.application.common.optional_conversion import optional_id
from app.domain.identity.entities import (
    CorporateMembership,
    UserAccount,
    UserInvitation,
)
from app.domain.identity.primitives import (
    AccountStatus,
    InvitationStatus,
    MembershipRole,
)


@dataclass(frozen=True)
class MembershipViewDto:
    """法人の利用者一覧・詳細で返す値。

    法人アクセス権の状態と、その土台にある個人アカウントの状態は別物である。
    片方だけを返すと「権限は有効だがアカウントが停止中」という組み合わせを
    呼び出し側が区別できない。外部主体識別子と招待の秘密は含めない。
    """

    id: str
    account_id: str
    person_id: str
    corporate_id: str
    status: AccountStatus
    account_status: AccountStatus
    role: MembershipRole
    store_ids: tuple[str, ...]
    staff_id: str | None

    @classmethod
    def from_entities(
        cls, membership: CorporateMembership, account: UserAccount
    ) -> MembershipViewDto:
        """権限とアカウントの状態を1つの公開値へまとめる。"""
        return cls(
            str(membership.id.value),
            str(account.id.value),
            str(account.person_id.value),
            str(membership.corporate_id.value),
            membership.status,
            account.status,
            membership.role,
            tuple(
                str(item.value)
                for item in sorted(membership.store_ids, key=lambda item: item.value)
            ),
            optional_id(membership.staff_id),
        )


@dataclass(frozen=True)
class InvitationViewDto:
    """招待の状態。ダイジェストも秘密も含めない。"""

    id: str
    person_id: str
    corporate_id: str
    status: InvitationStatus
    role: MembershipRole
    expires_at: datetime

    @classmethod
    def from_entity(cls, invitation: UserInvitation) -> InvitationViewDto:
        """受諾に使える値を漏らさずに状態だけを写す。"""
        return cls(
            str(invitation.id.value),
            str(invitation.person_id.value),
            str(invitation.corporate_id.value),
            invitation.status,
            invitation.role,
            invitation.expires_at,
        )
