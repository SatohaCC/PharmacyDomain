"""個人アカウントと法人アクセス権の保存契約。"""

from typing import Protocol

from app.domain.corporate.primitives import CorporateId
from app.domain.identity.account_person import AccountPerson
from app.domain.identity.invitation import InvitationDigest, UserInvitation
from app.domain.identity.membership import CorporateMembership
from app.domain.identity.primitives import (
    AccountPersonId,
    CorporateMembershipId,
    ExternalSubjectKey,
    UserAccountId,
    UserInvitationId,
)
from app.domain.identity.staff_person_link import StaffPersonLink
from app.domain.identity.user_account import UserAccount
from app.domain.staff.primitives import StaffId


class AccountPersonRepository(Protocol):
    """氏名から同一人物を推測せず本人IDで保存する。"""

    async def get(self, person_id: AccountPersonId) -> AccountPerson | None:
        """本人IDに一致する人を返す。"""
        ...

    async def save(self, person: AccountPerson) -> None:
        """本人情報を保存する。"""
        ...


class UserAccountRepository(Protocol):
    """人とアカウントの一対一対応を原子的に守る。"""

    async def get(self, account_id: UserAccountId) -> UserAccount | None:
        """アカウントIDで取得する。"""
        ...

    async def get_by_person(self, person_id: AccountPersonId) -> UserAccount | None:
        """本人に対応するアカウントを返す。"""
        ...

    async def save(self, account: UserAccount) -> None:
        """一人への二重作成と既存アカウントの別人への付け替えを拒否する。"""
        ...

    async def get_by_subject(self, subject: ExternalSubjectKey) -> UserAccount | None:
        """確認済み外部主体に対応するアカウントを返す。"""
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

    async def save(self, link: StaffPersonLink) -> None:
        """別人への付け替えを原子的に拒否する。"""
        ...


class UserInvitationRepository(Protocol):
    """秘密をハッシュとして保持する招待の保存境界。"""

    async def get(self, invitation_id: UserInvitationId) -> UserInvitation | None:
        """招待IDで取得する。"""
        ...

    async def find_by_digest(self, digest: InvitationDigest) -> UserInvitation | None:
        """照合用ハッシュで招待を取得する。"""
        ...

    async def save(self, invitation: UserInvitation) -> None:
        """招待を保存する。同時受諾は世代の不一致として拒否する。"""
        ...
