"""identityの保存・情報取得の抽象契約。"""

from __future__ import annotations

from collections.abc import Collection
from typing import Protocol

from app.domain.corporate.identifiers import CorporateId
from app.domain.identity.entities import (
    AccountPerson,
    CorporateMembership,
    StaffPersonLink,
    UserAccount,
    VendorOperator,
)
from app.domain.identity.identifiers import CorporateMembershipId, VendorOperatorId
from app.domain.identity.primitives import CorporateUserEmail, ExternalSubjectKey
from app.domain.shared.actor import AccountPersonId, UserAccountId
from app.domain.staff.identifiers import StaffId


class AccountPersonRepository(Protocol):
    """氏名から同一人物を推測せず本人IDで保存する。"""

    async def get(self, person_id: AccountPersonId) -> AccountPerson | None:
        """本人IDに一致する人を返す。"""
        ...

    async def find_for_corporate(
        self, corporate_id: CorporateId, person_id: AccountPersonId
    ) -> AccountPerson | None:
        """法人スコープ内で本人情報を取得する。"""
        ...

    async def save(self, person: AccountPerson) -> None:
        """本人情報を保存する。"""
        ...


class UserAccountRepository(Protocol):
    """人とアカウントの一対一対応を原子的に守る。"""

    async def get(self, account_id: UserAccountId) -> UserAccount | None:
        """アカウントIDで取得する。"""
        ...

    async def find_for_corporate(
        self, corporate_id: CorporateId, account_id: UserAccountId
    ) -> UserAccount | None:
        """法人スコープ内で個人アカウントを取得する。"""
        ...

    async def get_by_person(
        self, corporate_id: CorporateId, person_id: AccountPersonId
    ) -> UserAccount | None:
        """法人内の本人に対応するアカウントを返す。"""
        ...

    async def save(self, account: UserAccount) -> None:
        """一人への二重作成と既存アカウントの別人への付け替えを拒否する。"""
        ...

    async def get_by_subject(self, subject: ExternalSubjectKey) -> UserAccount | None:
        """確認済み外部主体に対応するアカウントを返す。"""
        ...

    async def list_by_ids(
        self, account_ids: Collection[UserAccountId]
    ) -> list[UserAccount]:
        """指定したアカウントを一度にまとめて返す。

        法人内の全アクセス権について1件ずつ引くと、管理者の人数に比例して
        往復が増える。存在しないIDは黙って除く。
        """
        ...


class CorporateMembershipRepository(Protocol):
    """個人アカウントが同時に使える法人は一つに制限する。"""

    async def get(
        self, membership_id: CorporateMembershipId
    ) -> CorporateMembership | None:
        """法人アクセス権IDで取得する。"""
        ...

    async def find_active_for_account(
        self, account_id: UserAccountId
    ) -> CorporateMembership | None:
        """有効な法人アクセス権を返す。"""
        ...

    async def save(self, membership: CorporateMembership) -> None:
        """有効法人の重複と同じStaffの別アカウントへの割当を原子的に拒否する。"""
        ...

    async def list_by_corporate(
        self, corporate_id: CorporateId
    ) -> list[CorporateMembership]:
        """停止履歴を含む法人のアクセス権を返す。"""
        ...

    async def find_by_staff(self, staff_id: StaffId) -> CorporateMembership | None:
        """スタッフに対応するアクセス権を返す。"""
        ...


class StaffPersonLinkRepository(Protocol):
    """Staffの本人対応を変更不可として保存する。"""

    async def get(self, staff_id: StaffId) -> StaffPersonLink | None:
        """スタッフIDで本人対応を取得する。"""
        ...

    async def find_for_corporate(
        self, corporate_id: CorporateId, staff_id: StaffId
    ) -> StaffPersonLink | None:
        """法人スコープ内でスタッフと本人の対応を取得する。"""
        ...

    async def save(self, link: StaffPersonLink) -> None:
        """別人への付け替えを原子的に拒否する。"""
        ...


class VendorOperatorRepository(Protocol):
    """運営者集約の永続化Protocol。"""

    async def get(self, operator_id: VendorOperatorId) -> VendorOperator | None:
        """運営者IDで取得する。"""
        ...

    async def get_by_subject(
        self, subject: ExternalSubjectKey
    ) -> VendorOperator | None:
        """外部主体で運営者を取得する。"""
        ...

    async def get_by_email(self, email: CorporateUserEmail) -> VendorOperator | None:
        """メールアドレスで運営者を取得する。"""
        ...

    async def save(self, operator: VendorOperator) -> None:
        """運営者を保存する。"""
        ...
