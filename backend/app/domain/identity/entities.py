"""identityのエンティティと集約。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from app.domain.corporate.identifiers import CorporateId
from app.domain.foundation.entity import AggregateRoot
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.identity.exceptions import IdentityConflictError
from app.domain.identity.identifiers import CorporateMembershipId, UserInvitationId
from app.domain.identity.primitives import (
    AccountStatus,
    ExternalSubjectKey,
    InvitationAddressee,
    InvitationDigest,
    InvitationStatus,
    MembershipRole,
)
from app.domain.shared.actor import AccountPersonId, UserAccountId
from app.domain.shared.person_name import PersonNames
from app.domain.staff.identifiers import StaffId
from app.domain.store.identifiers import StoreId


@dataclass(frozen=True, eq=False, kw_only=True)
class AccountPerson(AggregateRoot[AccountPersonId]):
    """アカウントを使用する一人の人。"""

    id: AccountPersonId
    names: PersonNames

    def change_names(self, names: PersonNames) -> AccountPerson:
        """本人の同一性を保ち氏名を変更する。"""
        return replace(self, names=names)


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

    def accept(self, *, now: datetime) -> UserInvitation:
        """受諾を記録する。受諾できる本人は ``person_id`` として招待自身が持つ。

        受諾者が名乗る本人を引数で受け取らない。外部の本人確認基盤が知っているのは
        自分が発行した主体までで、このシステムの本人IDは知らないため、呼び出し側は
        この招待の ``person_id`` しか渡せない。渡せない値との照合を残すと、恒真な
        判定が「守られているように見えて守られていない」表になる。
        """
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


@dataclass(frozen=True, eq=False, kw_only=True)
class StaffPersonLink(AggregateRoot[StaffId]):
    """同じStaffを別人へ付け替えないための独立した対応記録。"""

    id: StaffId
    corporate_id: CorporateId
    person_id: AccountPersonId


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
