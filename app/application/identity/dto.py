"""本人・アカウント管理の返却値。集約の変更メソッドを外側へ公開しない。"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.corporate.primitives import CorporateId
from app.domain.identity.account_person import AccountPerson
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
