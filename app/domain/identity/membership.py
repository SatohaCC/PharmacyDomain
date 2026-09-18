"""個人アカウントに与えた法人内アクセス権。"""

from dataclasses import dataclass, replace

from app.domain.corporate.primitives import CorporateId
from app.domain.foundation.entity import AggregateRoot
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.identity.primitives import (
    AccountStatus,
    CorporateMembershipId,
    MembershipRole,
    UserAccountId,
)
from app.domain.staff.primitives import StaffId
from app.domain.store.primitives import StoreId


@dataclass(frozen=True, eq=False, kw_only=True)
class CorporateMembership(AggregateRoot[CorporateMembershipId]):
    """法人と個人アカウントの関係。アカウントの所有者は変えない。"""

    id: CorporateMembershipId
    account_id: UserAccountId
    corporate_id: CorporateId
    role: MembershipRole
    store_ids: frozenset[StoreId]
    staff_id: StaffId | None = None
    status: AccountStatus = AccountStatus.ACTIVE

    def validate(self) -> None:
        """店舗ロールに法人内のスタッフ参照を要求する。"""
        if self.role != MembershipRole.CORPORATE_ADMIN and self.staff_id is None:
            raise DomainValidationError(
                "店舗ロールには本人に対応するスタッフが必要です。"
            )

    def suspend(self) -> CorporateMembership:
        """法人アクセス権だけを停止する。"""
        return replace(self, status=AccountStatus.SUSPENDED)

    def reactivate(self) -> CorporateMembership:
        """法人アクセス権を再開する。"""
        return replace(self, status=AccountStatus.ACTIVE)

    def change_access(
        self, *, role: MembershipRole, store_ids: frozenset[StoreId]
    ) -> CorporateMembership:
        """同一法人内のロールと店舗範囲を変更する。"""
        return replace(self, role=role, store_ids=store_ids)
