"""必ず本人を参照する個人アカウント。"""

from dataclasses import dataclass, replace

from app.domain.foundation.entity import AggregateRoot
from app.domain.identity.primitives import (
    AccountPersonId,
    AccountStatus,
    ExternalSubjectKey,
    UserAccountId,
)


@dataclass(frozen=True, eq=False, kw_only=True)
class UserAccount(AggregateRoot[UserAccountId]):
    """法人ではなく操作する本人に帰属するアカウント。"""

    id: UserAccountId
    person_id: AccountPersonId
    status: AccountStatus = AccountStatus.ACTIVE
    external_subject: ExternalSubjectKey | None = None
    is_vendor_admin: bool = False

    def suspend(self) -> UserAccount:
        """本人との対応を保持して利用を停止する。"""
        return replace(self, status=AccountStatus.SUSPENDED)

    def reactivate(self) -> UserAccount:
        """同じ本人の個人アカウントを再開する。"""
        return replace(self, status=AccountStatus.ACTIVE)
