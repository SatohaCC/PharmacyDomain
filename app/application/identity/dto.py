"""本人・アカウント管理の返却値。集約の変更メソッドを外側へ公開しない。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.application.access_control.models import ResolvedActorContext
from app.domain.corporate.primitives import CorporateId
from app.domain.identity.account_person import AccountPerson
from app.domain.identity.invitation import InvitationStatus, UserInvitation
from app.domain.identity.membership import CorporateMembership
from app.domain.identity.primitives import (
    AccountPersonId,
    AccountStatus,
    CorporateMembershipId,
    MembershipRole,
    UserAccountId,
    UserInvitationId,
)
from app.domain.identity.staff_person_link import StaffPersonLink
from app.domain.identity.user_account import UserAccount
from app.domain.shared.person_name import PersonNames
from app.domain.staff.primitives import StaffId
from app.domain.store.primitives import StoreId


@dataclass(frozen=True)
class PersonDto:
    """登録済み本人の識別と氏名。"""

    id: AccountPersonId
    names: PersonNames

    @classmethod
    def from_entity(cls, person: AccountPerson) -> PersonDto:
        """本人の値だけを写す。"""
        return cls(person.id, person.names)


@dataclass(frozen=True)
class AccountDto:
    """秘密を含まない個人アカウント。"""

    id: UserAccountId
    person_id: AccountPersonId
    status: AccountStatus

    @classmethod
    def from_entity(cls, account: UserAccount) -> AccountDto:
        """外部主体識別子を公開しない。"""
        return cls(account.id, account.person_id, account.status)


@dataclass(frozen=True)
class MembershipDto:
    """法人アクセス権の値。"""

    id: CorporateMembershipId
    account_id: UserAccountId
    corporate_id: CorporateId
    status: AccountStatus
    role: MembershipRole
    store_ids: frozenset[StoreId]
    staff_id: StaffId | None

    @classmethod
    def from_entity(cls, membership: CorporateMembership) -> MembershipDto:
        """権限を公開値として写す。"""
        return cls(
            membership.id,
            membership.account_id,
            membership.corporate_id,
            membership.status,
            membership.role,
            membership.store_ids,
            membership.staff_id,
        )


@dataclass(frozen=True)
class StaffPersonDto:
    """保存された本人とスタッフの対応。"""

    id: StaffId
    person_id: AccountPersonId
    corporate_id: CorporateId

    @classmethod
    def from_entity(cls, link: StaffPersonLink) -> StaffPersonDto:
        """対応の識別子だけを返す。"""
        return cls(link.id, link.person_id, link.corporate_id)


@dataclass(frozen=True)
class MembershipViewDto:
    """法人の利用者一覧・詳細で返す値。

    法人アクセス権の状態と、その土台にある個人アカウントの状態は別物である。
    片方だけを返すと「権限は有効だがアカウントが停止中」という組み合わせを
    呼び出し側が区別できない。外部主体識別子と招待の秘密は含めない。
    """

    id: CorporateMembershipId
    account_id: UserAccountId
    person_id: AccountPersonId
    corporate_id: CorporateId
    status: AccountStatus
    account_status: AccountStatus
    role: MembershipRole
    store_ids: tuple[StoreId, ...]
    staff_id: StaffId | None

    @classmethod
    def from_entities(
        cls, membership: CorporateMembership, account: UserAccount
    ) -> MembershipViewDto:
        """権限とアカウントの状態を1つの公開値へまとめる。"""
        return cls(
            membership.id,
            account.id,
            account.person_id,
            membership.corporate_id,
            membership.status,
            account.status,
            membership.role,
            tuple(sorted(membership.store_ids, key=lambda item: item.value)),
            membership.staff_id,
        )


@dataclass(frozen=True)
class InvitationViewDto:
    """招待の状態。ダイジェストも秘密も含めない。"""

    id: UserInvitationId
    person_id: AccountPersonId
    corporate_id: CorporateId
    status: InvitationStatus
    role: MembershipRole
    expires_at: datetime

    @classmethod
    def from_entity(cls, invitation: UserInvitation) -> InvitationViewDto:
        """受諾に使える値を漏らさずに状態だけを写す。"""
        return cls(
            invitation.id,
            invitation.person_id,
            invitation.corporate_id,
            invitation.status,
            invitation.role,
            invitation.expires_at,
        )


@dataclass(frozen=True)
class CurrentActorDto:
    """いま操作している本人・アカウント・権限の範囲。"""

    person_id: AccountPersonId
    account_id: UserAccountId
    membership_id: CorporateMembershipId | None
    corporate_id: CorporateId | None
    roles: tuple[str, ...]
    staff_id: StaffId | None
    store_ids: tuple[StoreId, ...]

    @classmethod
    def from_actor(cls, actor: ResolvedActorContext) -> CurrentActorDto:
        """解決済みActorを公開値へ写す。主体の識別子そのものは返さない。"""
        return cls(
            actor.person_id,
            actor.account_id,
            actor.membership_id,
            actor.corporate_id,
            tuple(sorted(role.value for role in actor.roles)),
            actor.staff_id,
            tuple(sorted(actor.store_ids, key=lambda item: item.value)),
        )
