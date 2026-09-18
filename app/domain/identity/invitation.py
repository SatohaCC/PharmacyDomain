"""指定された本人だけが受諾できる期限付き招待。"""

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum

from app.domain.corporate.primitives import CorporateId
from app.domain.foundation.entity import AggregateRoot
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.foundation.primitives.primitives import (
    BaseEmailAddress,
    BaseNormalizedString,
)
from app.domain.identity.exceptions import IdentityConflictError
from app.domain.identity.primitives import (
    AccountPersonId,
    MembershipRole,
    UserInvitationId,
)
from app.domain.staff.primitives import StaffId
from app.domain.store.primitives import StoreId


class InvitationStatus(StrEnum):
    """招待の受諾状態。"""

    PENDING = "pending"
    ACCEPTED = "accepted"
    CANCELLED = "cancelled"


class InvitationDigest(BaseNormalizedString):
    """招待秘密のダイジェスト。"""


class InvitationAddressee(BaseEmailAddress):
    """招待の宛先。本人確認の代用には使わない。"""


@dataclass(frozen=True, eq=False, kw_only=True)
class UserInvitation(AggregateRoot[UserInvitationId]):
    """本人と予定権限を固定した招待。"""

    id: UserInvitationId
    person_id: AccountPersonId
    corporate_id: CorporateId
    role: MembershipRole
    store_ids: frozenset[StoreId]
    secret_digest: InvitationDigest
    expires_at: datetime
    staff_id: StaffId | None = None
    status: InvitationStatus = InvitationStatus.PENDING
    addressee: InvitationAddressee | None = None

    def validate(self) -> None:
        """期限にタイムゾーンを要求する。"""
        if self.expires_at.utcoffset() is None:
            raise DomainValidationError("招待期限にはタイムゾーンが必要です。")

    def accept(self, *, person_id: AccountPersonId, now: datetime) -> UserInvitation:
        """検証済みの本人からの受諾を記録する。"""
        if person_id != self.person_id:
            raise IdentityConflictError(
                "招待された本人と確認済みの本人が一致しません。"
            )
        if self.status != InvitationStatus.PENDING or now >= self.expires_at:
            raise IdentityConflictError(
                "招待は使用済み、取消済み、または期限切れです。"
            )
        return replace(self, status=InvitationStatus.ACCEPTED)

    def cancel(self) -> UserInvitation:
        """未受諾の招待を取り消す。"""
        if self.status == InvitationStatus.ACCEPTED:
            raise IdentityConflictError("受諾済みの招待は取り消せません。")
        return replace(self, status=InvitationStatus.CANCELLED)
