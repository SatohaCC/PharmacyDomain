"""本人と個人アカウントの保存契約を持つテスト用Repository。"""

from app.domain.corporate.primitives import CorporateId
from app.domain.identity.account_person import AccountPerson
from app.domain.identity.exceptions import IdentityConflictError
from app.domain.identity.invitation import InvitationDigest, UserInvitation
from app.domain.identity.membership import CorporateMembership
from app.domain.identity.primitives import (
    AccountPersonId,
    AccountStatus,
    CorporateMembershipId,
    ExternalSubjectKey,
    UserAccountId,
    UserInvitationId,
)
from app.domain.identity.repository import (
    AccountPersonRepository,
    CorporateMembershipRepository,
    StaffPersonLinkRepository,
    UserAccountRepository,
    UserInvitationRepository,
)
from app.domain.identity.staff_person_link import StaffPersonLink
from app.domain.identity.user_account import UserAccount
from app.domain.staff.primitives import StaffId


class InMemoryAccountPersonRepository(AccountPersonRepository):
    """名前を一意キーにせず本人IDで管理する。"""

    def __init__(self) -> None:
        self.items: dict[AccountPersonId, AccountPerson] = {}

    async def get(self, person_id: AccountPersonId) -> AccountPerson | None:
        return self.items.get(person_id)

    async def save(self, person: AccountPerson) -> None:
        self.items[person.id] = person


class InMemoryUserAccountRepository(UserAccountRepository):
    """一人一アカウントと本人参照の不変性を守る。"""

    def __init__(self) -> None:
        self.items: dict[UserAccountId, UserAccount] = {}

    async def get(self, account_id: UserAccountId) -> UserAccount | None:
        return self.items.get(account_id)

    async def get_by_person(self, person_id: AccountPersonId) -> UserAccount | None:
        return next(
            (item for item in self.items.values() if item.person_id == person_id), None
        )

    async def save(self, account: UserAccount) -> None:
        previous = self.items.get(account.id)
        if previous is not None and previous.person_id != account.person_id:
            raise IdentityConflictError()
        if any(
            item.person_id == account.person_id and item.id != account.id
            for item in self.items.values()
        ):
            raise IdentityConflictError()
        if account.external_subject is not None and any(
            item.id != account.id and item.external_subject == account.external_subject
            for item in self.items.values()
        ):
            raise IdentityConflictError()
        self.items[account.id] = account

    async def get_by_subject(self, subject: ExternalSubjectKey) -> UserAccount | None:
        return next(
            (item for item in self.items.values() if item.external_subject == subject),
            None,
        )


class InMemoryCorporateMembershipRepository(CorporateMembershipRepository):
    """有効法人の上限とStaffへの一意な対応を確認する。"""

    def __init__(self) -> None:
        self.items: dict[CorporateMembershipId, CorporateMembership] = {}

    async def get(
        self, membership_id: CorporateMembershipId
    ) -> CorporateMembership | None:
        return self.items.get(membership_id)

    async def find_active_for_account(
        self, account_id: UserAccountId
    ) -> CorporateMembership | None:
        return next(
            (
                item
                for item in self.items.values()
                if item.account_id == account_id and item.status == AccountStatus.ACTIVE
            ),
            None,
        )

    async def save(self, membership: CorporateMembership) -> None:
        for existing in self.items.values():
            if existing.id == membership.id:
                continue
            if (
                existing.account_id == membership.account_id
                and existing.status == membership.status == AccountStatus.ACTIVE
            ):
                raise IdentityConflictError()
            if (
                membership.staff_id is not None
                and existing.staff_id == membership.staff_id
                and existing.account_id != membership.account_id
            ):
                raise IdentityConflictError()
        self.items[membership.id] = membership

    async def list_by_corporate(
        self, corporate_id: CorporateId
    ) -> list[CorporateMembership]:
        return [
            item for item in self.items.values() if item.corporate_id == corporate_id
        ]

    async def find_by_staff(self, staff_id: StaffId) -> CorporateMembership | None:
        return next(
            (item for item in self.items.values() if item.staff_id == staff_id), None
        )


class InMemoryStaffPersonLinkRepository(StaffPersonLinkRepository):
    """別人への付け替えを拒否する対応記録。"""

    def __init__(self) -> None:
        self.items: dict[StaffId, StaffPersonLink] = {}

    async def get(self, staff_id: StaffId) -> StaffPersonLink | None:
        return self.items.get(staff_id)

    async def save(self, link: StaffPersonLink) -> None:
        existing = self.items.get(link.id)
        if existing is not None and (
            existing.person_id != link.person_id
            or existing.corporate_id != link.corporate_id
        ):
            raise IdentityConflictError()
        self.items[link.id] = link


class InMemoryUserInvitationRepository(UserInvitationRepository):
    """招待秘密の平文を保存しない。"""

    def __init__(self) -> None:
        self.items: dict[UserInvitationId, UserInvitation] = {}

    async def get(self, invitation_id: UserInvitationId) -> UserInvitation | None:
        return self.items.get(invitation_id)

    async def find_by_digest(self, digest: InvitationDigest) -> UserInvitation | None:
        return next(
            (item for item in self.items.values() if item.secret_digest == digest), None
        )

    async def save(self, invitation: UserInvitation) -> None:
        self.items[invitation.id] = invitation
