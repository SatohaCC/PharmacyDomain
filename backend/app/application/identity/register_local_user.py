"""招待を介さず、本人のアカウントと法人権限を確定する。"""

from dataclasses import dataclass, field

from app.application.access_control.boundary import CorporateAccessBoundary
from app.application.access_control.models import Permission
from app.application.common.exceptions import NotFoundError
from app.application.common.organization_lock import OrganizationLock
from app.application.common.unit_of_work import UnitOfWork
from app.application.identity.local_authentication import CredentialWriter
from app.application.identity.support import (
    IdentityRepositories,
    validate_membership_target,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.identity.entities import CorporateMembership, UserAccount
from app.domain.identity.exceptions import IdentityConflictError
from app.domain.identity.identifiers import CorporateMembershipId
from app.domain.identity.primitives import ExternalSubjectKey, MembershipRole
from app.domain.shared.actor import AccountPersonId, UserAccountId
from app.domain.staff.identifiers import StaffId
from app.domain.staff.repositories import StaffRepository
from app.domain.store.identifiers import StoreId
from app.domain.store.repositories import StoreRepository


@dataclass(frozen=True, kw_only=True)
class RegisterLocalUserCommand:
    """本人と利用範囲を指定し、初期資格情報を発行する入力。"""

    corporate_id: str
    person_id: str
    login_id: str
    initial_password: str = field(repr=False)
    role: str = "corporate_admin"
    store_ids: tuple[str, ...] = ()
    staff_id: str | None = None


@dataclass(frozen=True, kw_only=True)
class RegisteredLocalUser:
    """登録完了したアカウント。パスワードは再表示しない。"""

    id: str
    login_id: str


class RegisterLocalUserUseCase:
    """権限と本人の整合を確認して、資格情報と利用権限を一括保存する。"""

    def __init__(
        self,
        repositories: IdentityRepositories,
        staff: StaffRepository,
        stores: StoreRepository,
        access: CorporateAccessBoundary,
        unit_of_work: UnitOfWork,
        lock: OrganizationLock,
        credentials: CredentialWriter,
    ) -> None:
        self._repositories = repositories
        self._staff = staff
        self._stores = stores
        self._access = access
        self._unit_of_work = unit_of_work
        self._lock = lock
        self._credentials = credentials

    async def execute(self, command: RegisterLocalUserCommand) -> RegisteredLocalUser:
        """認可された法人内の利用権限を確定する。ベンダー権限は発行しない。"""
        self._unit_of_work.ensure_active()
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._lock.acquire("identity")
        await self._lock.acquire(f"corporate:{corporate_id.value}")
        await self._access.require_active(
            corporate_id=corporate_id, permission=Permission.MANAGE_STAFF
        )
        person_id = AccountPersonId.parse(command.person_id)
        if await self._repositories.people.get(person_id) is None:
            raise NotFoundError("指定された本人が見つかりません。")
        if await self._repositories.accounts.get_by_person(person_id) is not None:
            raise IdentityConflictError("この本人には既にアカウントがあります。")
        role = MembershipRole(command.role)
        store_ids = frozenset(StoreId.parse(raw) for raw in command.store_ids)
        staff_id = StaffId.parse(command.staff_id) if command.staff_id else None
        await validate_membership_target(
            person_id=person_id,
            corporate_id=corporate_id,
            role=role,
            store_ids=store_ids,
            staff_id=staff_id,
            staff=self._staff,
            stores=self._stores,
            links=self._repositories.links,
        )
        account_id = UserAccountId.generate()
        subject = f"local:{account_id.value}"
        account = UserAccount(
            id=account_id,
            person_id=person_id,
            external_subject=ExternalSubjectKey(subject),
        )
        membership = CorporateMembership(
            id=CorporateMembershipId.generate(),
            account_id=account_id,
            corporate_id=corporate_id,
            role=role,
            store_ids=store_ids,
            staff_id=staff_id,
        )
        await self._repositories.accounts.save(account)
        await self._credentials.issue(
            command.login_id, command.initial_password, subject
        )
        await self._repositories.memberships.save(membership)
        return RegisteredLocalUser(
            id=str(account_id.value), login_id=command.login_id.strip().lower()
        )
