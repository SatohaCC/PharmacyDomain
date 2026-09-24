"""本人を固定した法人招待を発行するユースケース。"""

import secrets
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256

from app.application.access_control.boundary import CorporateAccessBoundary
from app.application.access_control.models import Permission
from app.application.common.clock import Clock
from app.application.common.exceptions import NotFoundError
from app.application.common.organization_lock import OrganizationLock
from app.application.common.unit_of_work import UnitOfWork
from app.application.identity.support import (
    IdentityRepositories,
    validate_membership_target,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.identity.invitation import (
    InvitationAddressee,
    InvitationDigest,
    UserInvitation,
)
from app.domain.identity.primitives import (
    AccountPersonId,
    MembershipRole,
    UserInvitationId,
)
from app.domain.staff.primitives import StaffId
from app.domain.staff.repository import StaffRepository
from app.domain.store.primitives import StoreId
from app.domain.store.repository import StoreRepository


@dataclass(frozen=True, kw_only=True)
class InviteUserCommand:
    """本人を固定した法人招待の入力。"""

    corporate_id: str
    person_id: str
    addressee: str
    role: MembershipRole
    expires_at: datetime
    store_ids: tuple[str, ...] = ()
    staff_id: str | None = None


@dataclass(frozen=True, kw_only=True)
class IssuedInvitation:
    """発行時だけ返す招待秘密。"""

    id: str
    secret: str


class InviteUserUseCase:
    """受諾できる本人と権限の範囲を、発行の時点で固定する。

    秘密は発行時にだけ返し、保存はダイジェストだけにする。後から再取得できる形に
    すると、台帳を読める者が誰の招待でも受諾できてしまう。
    """

    def __init__(
        self,
        repositories: IdentityRepositories,
        staff: StaffRepository,
        stores: StoreRepository,
        access: CorporateAccessBoundary,
        clock: Clock,
        unit_of_work: UnitOfWork,
        lock: OrganizationLock,
    ) -> None:
        self._repositories = repositories
        self._staff = staff
        self._stores = stores
        self._access = access
        self._clock = clock
        self._unit_of_work = unit_of_work
        self._lock = lock

    async def execute(self, command: InviteUserCommand) -> IssuedInvitation:
        """本人と許可範囲を確認して招待を発行する。"""
        self._unit_of_work.ensure_active()
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._lock.acquire("identity")
        await self._access.require_active(
            corporate_id=corporate_id, permission=Permission.MANAGE_STAFF
        )
        person_id = AccountPersonId.parse(command.person_id)
        if await self._repositories.people.get(person_id) is None:
            raise NotFoundError("指定された本人が見つかりません。")
        if (
            command.expires_at.utcoffset() is None
            or command.expires_at <= self._clock.now()
        ):
            raise DomainValidationError(
                "招待期限はタイムゾーン付きの未来時刻にしてください。"
            )
        store_ids = frozenset(StoreId.parse(raw) for raw in command.store_ids)
        staff_id = (
            StaffId.parse(command.staff_id) if command.staff_id is not None else None
        )
        await validate_membership_target(
            person_id=person_id,
            corporate_id=corporate_id,
            role=command.role,
            store_ids=store_ids,
            staff_id=staff_id,
            staff=self._staff,
            stores=self._stores,
            links=self._repositories.links,
        )
        secret = secrets.token_urlsafe(32)
        invitation = UserInvitation(
            id=UserInvitationId.generate(),
            person_id=person_id,
            corporate_id=corporate_id,
            role=command.role,
            store_ids=store_ids,
            staff_id=staff_id,
            expires_at=command.expires_at,
            addressee=InvitationAddressee(command.addressee),
            secret_digest=InvitationDigest(sha256(secret.encode()).hexdigest()),
        )
        await self._repositories.invitations.save(invitation)
        return IssuedInvitation(id=str(invitation.id.value), secret=secret)


__all__ = ["InviteUserCommand", "InviteUserUseCase", "IssuedInvitation"]
