"""本人指定の招待と法人アクセス権を管理する公開契約。"""

import secrets
from dataclasses import dataclass, replace
from datetime import datetime
from hashlib import sha256

from app.application.access_control import (
    AuthorizationService,
    CorporateAccessBoundary,
    Permission,
)
from app.application.common import UnitOfWork
from app.application.common.clock import Clock
from app.application.common.exceptions import NotFoundError
from app.application.common.organization_lock import OrganizationLock
from app.application.common.pagination import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    Page,
)
from app.application.identity.dto import (
    AccountDto,
    InvitationViewDto,
    MembershipDto,
    MembershipViewDto,
    PersonDto,
    StaffPersonDto,
)
from app.application.identity.resolve_actor import VerifiedIdentity
from app.domain.corporate.primitives import CorporateId
from app.domain.corporate.repository import CorporateRepository
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.identity.account_person import AccountPerson
from app.domain.identity.administrator_service import LastAdministratorService
from app.domain.identity.exceptions import IdentityConflictError
from app.domain.identity.invitation import (
    InvitationAddressee,
    InvitationDigest,
    UserInvitation,
)
from app.domain.identity.membership import CorporateMembership
from app.domain.identity.primitives import (
    AccountPersonId,
    AccountStatus,
    CorporateMembershipId,
    ExternalSubjectKey,
    MembershipRole,
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
from app.domain.shared.person_name import PersonNames
from app.domain.staff.primitives import StaffId
from app.domain.staff.repository import StaffRepository
from app.domain.store.primitives import StoreId
from app.domain.store.repository import StoreRepository


@dataclass(frozen=True)
class IdentityRepositories:
    """同じUoWに接続されたIdentityの保存境界。"""

    people: AccountPersonRepository
    accounts: UserAccountRepository
    memberships: CorporateMembershipRepository
    links: StaffPersonLinkRepository
    invitations: UserInvitationRepository


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


class IdentityManagementUseCase:
    """本人と所属を分離して招待・アクセス状態を管理する。"""

    def __init__(
        self,
        repositories: IdentityRepositories,
        staff: StaffRepository,
        stores: StoreRepository,
        access: CorporateAccessBoundary,
        clock: Clock,
        unit_of_work: UnitOfWork,
        lock: OrganizationLock,
        corporates: CorporateRepository,
    ) -> None:
        self.repositories = repositories
        self._staff = staff
        self._stores = stores
        self._access = access
        self._clock = clock
        self._unit_of_work = unit_of_work
        self._lock = lock
        self._corporates = corporates

    async def register_person(
        self, corporate_id: str | None, names: PersonNames
    ) -> PersonDto:
        """招待に必要な本人記録を名前から統合せず新規作成する。"""
        self._unit_of_work.ensure_active()
        if corporate_id is None:
            AuthorizationService(self._access.actor).require_vendor_system_admin(
                permission=Permission.REGISTER_CORPORATE
            )
        else:
            await self._access.require_active(
                corporate_id=CorporateId.parse(corporate_id),
                permission=Permission.MANAGE_STAFF,
            )
        person = AccountPerson(id=AccountPersonId.generate(), names=names)
        await self.repositories.people.save(person)
        return PersonDto.from_entity(person)

    async def link_staff(
        self, corporate_id: str, person_id: str, staff_id: str
    ) -> StaffPersonDto:
        """既存の本人とStaffを管理者が対応させ、別人への付け替えを拒否する。"""
        self._unit_of_work.ensure_active()
        corporate = CorporateId.parse(corporate_id)
        await self._lock.acquire("identity")
        await self._lock.acquire(f"corporate:{corporate.value}")
        await self._access.require_active(
            corporate_id=corporate, permission=Permission.MANAGE_STAFF
        )
        person = await self.repositories.people.get(AccountPersonId.parse(person_id))
        staff = await self._staff.get(
            corporate_id=corporate, staff_id=StaffId.parse(staff_id)
        )
        if person is None or staff is None or staff.corporate_id != corporate:
            raise NotFoundError()
        existing = await self.repositories.links.get(staff.id)
        if existing is not None:
            if existing.person_id != person.id or existing.corporate_id != corporate:
                raise IdentityConflictError(
                    "スタッフを別の本人へ付け替えることはできません。"
                )
            return StaffPersonDto.from_entity(existing)
        link = StaffPersonLink(id=staff.id, corporate_id=corporate, person_id=person.id)
        await self.repositories.links.save(link)
        return StaffPersonDto.from_entity(link)

    async def cancel_invitation(self, corporate_id: str, invitation_id: str) -> None:
        """自法人の未受諾招待を取り消す。"""
        self._unit_of_work.ensure_active()
        corporate = CorporateId.parse(corporate_id)
        await self._lock.acquire("identity")
        await self._access.require_active(
            corporate_id=corporate, permission=Permission.MANAGE_STAFF
        )
        invitation = await self.repositories.invitations.get(
            UserInvitationId.parse(invitation_id)
        )
        if invitation is None or invitation.corporate_id != corporate:
            raise NotFoundError()
        await self.repositories.invitations.save(invitation.cancel())

    async def change_membership(
        self,
        corporate_id: str,
        membership_id: str,
        *,
        status: AccountStatus | None = None,
        role: MembershipRole | None = None,
        store_ids: tuple[str, ...] | None = None,
    ) -> MembershipDto:
        """最後の管理者と本人対応を守って法人アクセス権を変更する。"""
        self._unit_of_work.ensure_active()
        corporate = CorporateId.parse(corporate_id)
        await self._lock.acquire("identity")
        await self._lock.acquire(f"corporate:{corporate.value}")
        await self._access.require_active(
            corporate_id=corporate, permission=Permission.MANAGE_STAFF
        )
        membership = await self.repositories.memberships.get(
            CorporateMembershipId.parse(membership_id)
        )
        if membership is None or membership.corporate_id != corporate:
            raise NotFoundError()
        account = await self.repositories.accounts.get(membership.account_id)
        if account is None:
            raise NotFoundError()
        updated = replace(
            membership,
            status=status if status is not None else membership.status,
            role=role if role is not None else membership.role,
            store_ids=frozenset(StoreId.parse(item) for item in store_ids)
            if store_ids is not None
            else membership.store_ids,
        )
        if updated.status == AccountStatus.ACTIVE:
            if account.status != AccountStatus.ACTIVE:
                raise IdentityConflictError(
                    "停止中のアカウントへアクセス権を有効化できません。"
                )
            await self.validate_target(
                account.person_id,
                corporate,
                updated.role,
                updated.store_ids,
                updated.staff_id,
            )
        await self.ensure_administrator(corporate, updated_membership=updated)
        await self.repositories.memberships.save(updated)
        return MembershipDto.from_entity(updated)

    async def suspend_account(self, account_id: str) -> AccountDto:
        """ベンダーが個人アカウント全体を停止する。"""
        self._unit_of_work.ensure_active()
        AuthorizationService(self._access.actor).require_vendor_system_admin(
            permission=Permission.REGISTER_CORPORATE
        )
        await self._lock.acquire("identity")
        account = await self.repositories.accounts.get(UserAccountId.parse(account_id))
        if account is None:
            raise NotFoundError()
        updated = account.suspend()
        membership = await self.repositories.memberships.find_active_for_account(
            account.id
        )
        if membership is not None:
            await self._lock.acquire(f"corporate:{membership.corporate_id.value}")
            await self.ensure_administrator(
                membership.corporate_id, updated_account=updated
            )
        await self.repositories.accounts.save(updated)
        return AccountDto.from_entity(updated)

    async def ensure_administrator(
        self,
        corporate_id: CorporateId,
        *,
        updated_membership: CorporateMembership | None = None,
        updated_account: UserAccount | None = None,
    ) -> None:
        """ロック内で変更前後の実効管理者数を確認する。"""
        memberships = await self.repositories.memberships.list_by_corporate(
            corporate_id
        )
        accounts = []
        for account_id in {item.account_id for item in memberships}:
            account = await self.repositories.accounts.get(account_id)
            if account is not None:
                accounts.append(account)
        after_memberships = [
            updated_membership
            if updated_membership is not None and item.id == updated_membership.id
            else item
            for item in memberships
        ]
        after_accounts = [
            updated_account
            if updated_account is not None and item.id == updated_account.id
            else item
            for item in accounts
        ]
        LastAdministratorService().ensure_preserved(
            corporate_id=corporate_id,
            previous_memberships=memberships,
            previous_accounts=accounts,
            updated_memberships=after_memberships,
            updated_accounts=after_accounts,
        )

    async def invite(self, command: InviteUserCommand) -> IssuedInvitation:
        """本人と許可範囲を確認して招待を発行する。"""
        self._unit_of_work.ensure_active()
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._lock.acquire("identity")
        await self._access.require_active(
            corporate_id=corporate_id, permission=Permission.MANAGE_STAFF
        )
        person_id = AccountPersonId.parse(command.person_id)
        if await self.repositories.people.get(person_id) is None:
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
        await self.validate_target(
            person_id, corporate_id, command.role, store_ids, staff_id
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
        await self.repositories.invitations.save(invitation)
        return IssuedInvitation(id=str(invitation.id.value), secret=secret)

    async def accept(self, secret: str, identity: VerifiedIdentity) -> AccountDto:
        """検証済み本人の招待を一度だけ受諾する。"""
        self._unit_of_work.ensure_active()
        await self._lock.acquire("identity")
        invitation = await self.repositories.invitations.find_by_digest(
            InvitationDigest(sha256(secret.encode()).hexdigest())
        )
        if invitation is None:
            raise IdentityConflictError("この招待は利用できません。")
        accepted = invitation.accept(
            person_id=identity.person_id, now=self._clock.now()
        )
        await self._lock.acquire(f"corporate:{invitation.corporate_id.value}")
        corporate = await self._corporates.get(invitation.corporate_id)
        if corporate is None or not corporate.is_active:
            raise IdentityConflictError("招待先の法人は利用できません。")
        if await self.repositories.people.get(identity.person_id) is None:
            raise IdentityConflictError("招待された本人を確認できません。")
        await self.validate_target(
            invitation.person_id,
            invitation.corporate_id,
            invitation.role,
            invitation.store_ids,
            invitation.staff_id,
        )
        subject = ExternalSubjectKey(identity.principal_id)
        bound = await self.repositories.accounts.get_by_subject(subject)
        if bound is not None and bound.person_id != identity.person_id:
            raise IdentityConflictError("外部主体は別の本人に対応しています。")
        account = await self.repositories.accounts.get_by_person(identity.person_id)
        if account is None:
            account = UserAccount(
                id=UserAccountId.generate(),
                person_id=identity.person_id,
                external_subject=subject,
            )
        elif account.status != AccountStatus.ACTIVE or (
            account.external_subject is not None and account.external_subject != subject
        ):
            raise IdentityConflictError(
                "この個人アカウントは招待の受諾に利用できません。"
            )
        else:
            account = replace(account, external_subject=subject)
        if (
            await self.repositories.memberships.find_active_for_account(account.id)
            is not None
        ):
            raise IdentityConflictError("既に有効な法人アクセス権があります。")
        previous = next(
            (
                item
                for item in await self.repositories.memberships.list_by_corporate(
                    invitation.corporate_id
                )
                if item.account_id == account.id
            ),
            None,
        )
        membership = CorporateMembership(
            id=previous.id if previous else CorporateMembershipId.generate(),
            account_id=account.id,
            corporate_id=invitation.corporate_id,
            role=invitation.role,
            store_ids=invitation.store_ids,
            staff_id=invitation.staff_id,
        )
        await self.repositories.accounts.save(account)
        await self.repositories.memberships.save(membership)
        await self.repositories.invitations.save(accepted)
        return AccountDto.from_entity(account)

    async def list_users(
        self,
        corporate_id: str,
        *,
        after: str | None = None,
        limit: int = DEFAULT_PAGE_SIZE,
    ) -> Page[MembershipViewDto]:
        """自法人のアクセス権をID順で返す。秘密・外部主体は返さない。"""
        corporate = CorporateId.parse(corporate_id)
        await self._access.require_active(
            corporate_id=corporate, permission=Permission.MANAGE_STAFF
        )
        if not 1 <= limit <= MAX_PAGE_SIZE:
            raise DomainValidationError(
                f"件数は1から{MAX_PAGE_SIZE}で指定してください。"
            )
        after_id = CorporateMembershipId.parse(after) if after else None
        rows = sorted(
            await self.repositories.memberships.list_by_corporate(corporate),
            key=lambda item: item.id.value,
        )
        rows = [
            item for item in rows if after_id is None or item.id.value > after_id.value
        ]
        page = rows[:limit]
        return Page(
            items=tuple([await self._public_membership(item) for item in page]),
            next_cursor=str(page[-1].id.value) if len(rows) > limit else None,
        )

    async def get_user(
        self, corporate_id: str, membership_id: str
    ) -> MembershipViewDto:
        """本人を広域検索せず、対象法人に属するアクセス権から参照する。"""
        corporate = CorporateId.parse(corporate_id)
        await self._access.require_active(
            corporate_id=corporate, permission=Permission.MANAGE_STAFF
        )
        membership = await self.repositories.memberships.get(
            CorporateMembershipId.parse(membership_id)
        )
        if membership is None or membership.corporate_id != corporate:
            raise NotFoundError()
        return await self._public_membership(membership)

    async def _public_membership(
        self, membership: CorporateMembership
    ) -> MembershipViewDto:
        account = await self.repositories.accounts.get(membership.account_id)
        if account is None:
            raise NotFoundError()
        return MembershipViewDto.from_entities(membership, account)

    async def get_invitation(
        self, corporate_id: str, invitation_id: str
    ) -> InvitationViewDto:
        """招待の状態だけを返し、ハッシュも秘密も返さない。"""
        corporate = CorporateId.parse(corporate_id)
        await self._access.require_active(
            corporate_id=corporate, permission=Permission.MANAGE_STAFF
        )
        invitation = await self.repositories.invitations.get(
            UserInvitationId.parse(invitation_id)
        )
        if invitation is None or invitation.corporate_id != corporate:
            raise NotFoundError()
        return InvitationViewDto.from_entity(invitation)

    async def reactivate_account(self, account_id: str) -> AccountDto:
        """本人への参照を維持したまま個人アカウントをベンダーが再開する。"""
        self._unit_of_work.ensure_active()
        AuthorizationService(self._access.actor).require_vendor_system_admin(
            permission=Permission.REGISTER_CORPORATE
        )
        await self._lock.acquire("identity")
        account = await self.repositories.accounts.get(UserAccountId.parse(account_id))
        if account is None:
            raise NotFoundError()
        updated = account.reactivate()
        await self.repositories.accounts.save(updated)
        return AccountDto.from_entity(updated)

    async def validate_target(
        self,
        person_id: AccountPersonId,
        corporate_id: CorporateId,
        role: MembershipRole,
        store_ids: frozenset[StoreId],
        staff_id: StaffId | None,
    ) -> None:
        """本人・Staff・許可店舗の法人と対応を確認する。"""
        if role != MembershipRole.CORPORATE_ADMIN and staff_id is None:
            raise DomainValidationError("店舗ロールにはスタッフ参照が必要です。")
        for store_id in store_ids:
            store = await self._stores.get(store_id)
            if store is None or store.corporate_id != corporate_id:
                raise NotFoundError("指定された店舗が見つかりません。")
        if staff_id is not None:
            staff = await self._staff.get(corporate_id=corporate_id, staff_id=staff_id)
            if staff is None or staff.corporate_id != corporate_id:
                raise NotFoundError("指定されたスタッフが見つかりません。")
            link = await self.repositories.links.get(staff_id)
            if (
                link is None
                or link.person_id != person_id
                or link.corporate_id != corporate_id
                or not staff.is_active
            ):
                raise IdentityConflictError("有効な本人とスタッフの対応が必要です。")
