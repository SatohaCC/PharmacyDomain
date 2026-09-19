"""本人・アカウント管理の返却値。集約の変更メソッドを外側へ公開しない。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.application.access_control.models import ResolvedActorContext
from app.application.common.optional_conversion import optional_id
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


@dataclass(frozen=True)
class CurrentActorDto:
    """いま操作している本人・アカウント・権限の範囲。"""

    person_id: str
    account_id: str
    membership_id: str | None
    corporate_id: str | None
    roles: tuple[str, ...]
    staff_id: str | None
    store_ids: tuple[str, ...]

    @classmethod
    def from_actor(cls, actor: ResolvedActorContext) -> CurrentActorDto:
        """解決済みActorを公開値へ写す。主体の識別子そのものは返さない。"""
        return cls(
            str(actor.person_id.value),
            str(actor.account_id.value),
            optional_id(actor.membership_id),
            optional_id(actor.corporate_id),
            tuple(sorted(role.value for role in actor.roles)),
            optional_id(actor.staff_id),
            tuple(
                str(item.value)
                for item in sorted(actor.store_ids, key=lambda item: item.value)
            ),
        )
