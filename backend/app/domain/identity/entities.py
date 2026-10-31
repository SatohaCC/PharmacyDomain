"""identityのエンティティと集約。"""

from __future__ import annotations

from dataclasses import dataclass, replace

from app.domain.corporate.identifiers import CorporateId
from app.domain.foundation.entity import AggregateRoot
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.identity.identifiers import CorporateMembershipId, VendorOperatorId
from app.domain.identity.primitives import (
    AccountStatus,
    CorporateUserEmail,
    ExternalSubjectKey,
    MembershipRole,
)
from app.domain.shared.actor import AccountPersonId, UserAccountId
from app.domain.shared.person_name import PersonNames
from app.domain.staff.identifiers import StaffId
from app.domain.store.identifiers import StoreId


@dataclass(frozen=True, eq=False, kw_only=True)
class AccountPerson(AggregateRoot[AccountPersonId]):
    """特定法人に所属するアカウントを使用する一人の人。"""

    id: AccountPersonId
    corporate_id: CorporateId
    names: PersonNames

    def change_names(self, names: PersonNames) -> AccountPerson:
        """本人の同一性を保ち氏名を変更する。"""
        return replace(self, names=names)


@dataclass(frozen=True, eq=False, kw_only=True)
class VendorOperator(AggregateRoot[VendorOperatorId]):
    """運営者（システム管理者）集約。特定法人に属さず独立して存在する。"""

    id: VendorOperatorId
    email: CorporateUserEmail
    external_subject: ExternalSubjectKey
    is_active: bool = True

    def deactivate(self) -> VendorOperator:
        """運営者を停止する。"""
        return replace(self, is_active=False)

    def reactivate(self) -> VendorOperator:
        """運営者を再開する。"""
        return replace(self, is_active=True)


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
    suspended_store_ids: frozenset[StoreId] = frozenset()

    def validate(self) -> None:
        """店舗ロールに法人内のスタッフ参照を要求する。"""
        if not self.suspended_store_ids <= self.store_ids:
            raise DomainValidationError("停止対象は所属店舗から指定してください。")
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
        return replace(
            self,
            role=role,
            store_ids=store_ids,
            suspended_store_ids=self.suspended_store_ids & store_ids,
        )

    @property
    def active_store_ids(self) -> frozenset[StoreId]:
        """法人管理権限とは独立した、有効な店舗利用権限を返す。"""
        return self.store_ids - self.suspended_store_ids

    def change_store_access(
        self, *, store_id: StoreId, is_active: bool
    ) -> CorporateMembership:
        """他店舗の利用と法人権限を保ち、一店舗の利用状態だけを変更する。"""
        if store_id not in self.store_ids:
            raise DomainValidationError("対象店舗への所属がありません。")
        suspended = (
            self.suspended_store_ids - {store_id}
            if is_active
            else self.suspended_store_ids | {store_id}
        )
        return replace(self, suspended_store_ids=suspended)

    def assign_staff(self, staff_id: StaffId) -> CorporateMembership:
        """初期管理者などに後からスタッフ参照を紐付ける。"""
        if self.staff_id is not None:
            raise DomainValidationError("スタッフは既に設定されています。")
        updated = replace(self, staff_id=staff_id)
        updated.validate()
        return updated


@dataclass(frozen=True, eq=False, kw_only=True)
class StaffPersonLink(AggregateRoot[StaffId]):
    """同じStaffを別人へ付け替えないための独立した対応記録。"""

    id: StaffId
    corporate_id: CorporateId
    person_id: AccountPersonId


@dataclass(frozen=True, eq=False, kw_only=True)
class UserAccount(AggregateRoot[UserAccountId]):
    """特定法人内の個人アカウント。"""

    id: UserAccountId
    corporate_id: CorporateId
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
