"""Applicationのdtoを定義する。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control.boundary_models import ResolvedActorContext
from app.application.common.optional_conversion import optional_id
from app.domain.corporate.identifiers import CorporateId
from app.domain.identity.entities import (
    AccountPerson,
    CorporateMembership,
    StaffPersonLink,
    UserAccount,
)
from app.domain.identity.identifiers import CorporateMembershipId
from app.domain.identity.primitives import AccountStatus, MembershipRole
from app.domain.shared.actor import AccountPersonId, UserAccountId
from app.domain.shared.person_name import PersonNames
from app.domain.staff.identifiers import StaffId
from app.domain.store.identifiers import StoreId


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
