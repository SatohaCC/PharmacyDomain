"""本人と個人アカウントの保存契約を持つテスト用Repository。"""

from collections.abc import Collection

from app.application.identity.boundary_interfaces.local_authentication import (
    CredentialWriter,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.identity.entities import (
    AccountPerson,
    CorporateMembership,
    StaffPersonLink,
    UserAccount,
    VendorOperator,
)
from app.domain.identity.exceptions import IdentityConflictError
from app.domain.identity.identifiers import CorporateMembershipId, VendorOperatorId
from app.domain.identity.primitives import (
    AccountStatus,
    CorporateUserEmail,
    ExternalSubjectKey,
)
from app.domain.identity.repositories import (
    AccountPersonRepository,
    CorporateMembershipRepository,
    StaffPersonLinkRepository,
    UserAccountRepository,
    VendorOperatorRepository,
)
from app.domain.shared.actor import AccountPersonId, UserAccountId
from app.domain.staff.identifiers import StaffId


class InMemoryAccountPersonRepository(AccountPersonRepository):
    """名前を一意キーにせず本人IDで管理する。"""

    def __init__(self) -> None:
        self.items: dict[AccountPersonId, AccountPerson] = {}

    async def get(self, person_id: AccountPersonId) -> AccountPerson | None:
        return self.items.get(person_id)

    async def find_for_corporate(
        self, corporate_id: CorporateId, person_id: AccountPersonId
    ) -> AccountPerson | None:
        person = self.items.get(person_id)
        if person is not None and person.corporate_id == corporate_id:
            return person
        return None

    async def save(self, person: AccountPerson) -> None:
        self.items[person.id] = person


class InMemoryUserAccountRepository(UserAccountRepository):
    """一人一アカウントと本人参照の不変性を守る。"""

    def __init__(self) -> None:
        self.items: dict[UserAccountId, UserAccount] = {}

    async def get(self, account_id: UserAccountId) -> UserAccount | None:
        return self.items.get(account_id)

    async def find_for_corporate(
        self, corporate_id: CorporateId, account_id: UserAccountId
    ) -> UserAccount | None:
        account = self.items.get(account_id)
        if account is not None and account.corporate_id == corporate_id:
            return account
        return None

    async def get_by_person(
        self, corporate_id: CorporateId, person_id: AccountPersonId
    ) -> UserAccount | None:
        return next(
            (
                item
                for item in self.items.values()
                if item.corporate_id == corporate_id and item.person_id == person_id
            ),
            None,
        )

    async def save(self, account: UserAccount) -> None:
        previous = self.items.get(account.id)
        if previous is not None and (
            previous.person_id != account.person_id
            or previous.corporate_id != account.corporate_id
            or (
                previous.external_subject is not None
                and previous.external_subject != account.external_subject
            )
        ):
            raise IdentityConflictError()
        if any(
            item.corporate_id == account.corporate_id
            and item.person_id == account.person_id
            and item.id != account.id
            for item in self.items.values()
        ):
            raise IdentityConflictError()
        if account.external_subject is not None and any(
            item.id != account.id
            and item.corporate_id == account.corporate_id
            and item.external_subject == account.external_subject
            for item in self.items.values()
        ):
            raise IdentityConflictError()
        self.items[account.id] = account

    async def get_by_subject(self, subject: ExternalSubjectKey) -> UserAccount | None:
        return next(
            (item for item in self.items.values() if item.external_subject == subject),
            None,
        )

    async def list_by_ids(
        self, account_ids: Collection[UserAccountId]
    ) -> list[UserAccount]:
        wanted = set(account_ids)
        return [item for item in self.items.values() if item.id in wanted]


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

    async def find_for_corporate(
        self, corporate_id: CorporateId, staff_id: StaffId
    ) -> StaffPersonLink | None:
        link = self.items.get(staff_id)
        if link is not None and link.corporate_id == corporate_id:
            return link
        return None

    async def save(self, link: StaffPersonLink) -> None:
        existing = self.items.get(link.id)
        if existing is not None and (
            existing.person_id != link.person_id
            or existing.corporate_id != link.corporate_id
        ):
            raise IdentityConflictError()
        self.items[link.id] = link


class InMemoryVendorOperatorRepository(VendorOperatorRepository):
    """インメモリ運営者リポジトリ。"""

    def __init__(self) -> None:
        self.items: dict[VendorOperatorId, VendorOperator] = {}

    async def get(self, operator_id: VendorOperatorId) -> VendorOperator | None:
        return self.items.get(operator_id)

    async def get_by_subject(
        self, subject: ExternalSubjectKey
    ) -> VendorOperator | None:
        return next(
            (item for item in self.items.values() if item.external_subject == subject),
            None,
        )

    async def get_by_email(self, email: CorporateUserEmail) -> VendorOperator | None:
        return next(
            (item for item in self.items.values() if item.email == email),
            None,
        )

    async def save(self, operator: VendorOperator) -> None:
        for existing in self.items.values():
            if existing.id != operator.id:
                if existing.email == operator.email:
                    raise IdentityConflictError(
                        "このメールアドレスの運営者は既に登録されています。"
                    )
                if existing.external_subject == operator.external_subject:
                    raise IdentityConflictError(
                        "この外部主体の運営者は既に登録されています。"
                    )
        self.items[operator.id] = operator


class FakeCredentialWriter(CredentialWriter):
    """インメモリ資格情報書き込み。"""

    def __init__(self) -> None:
        self.issued: list[tuple[CorporateId, str, str, str]] = []

    async def issue(
        self, corporate_id: CorporateId, email: str, password: str, subject: str
    ) -> None:
        self.issued.append((corporate_id, email, password, subject))
