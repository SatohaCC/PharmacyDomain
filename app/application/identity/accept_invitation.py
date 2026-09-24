"""検証済みの外部主体が、招待に書かれた本人として受諾するユースケース。"""

from dataclasses import replace
from hashlib import sha256

from app.application.common.clock import Clock
from app.application.common.organization_lock import OrganizationLock
from app.application.common.unit_of_work import UnitOfWork
from app.application.identity.dto import AccountDto
from app.application.identity.resolve_actor import VerifiedSubject
from app.application.identity.support import (
    IdentityRepositories,
    validate_membership_target,
)
from app.domain.corporate.repository import CorporateRepository
from app.domain.identity.exceptions import IdentityConflictError
from app.domain.identity.invitation import InvitationDigest, UserInvitation
from app.domain.identity.membership import CorporateMembership
from app.domain.identity.primitives import (
    AccountPersonId,
    AccountStatus,
    CorporateMembershipId,
    ExternalSubjectKey,
    UserAccountId,
)
from app.domain.identity.user_account import UserAccount
from app.domain.staff.repository import StaffRepository
from app.domain.store.repository import StoreRepository


class AcceptInvitationUseCase:
    """招待の秘密と本人確認の両方が揃ったときだけアクセス権を与える。

    このユースケースだけは、アカウントがこの操作で初めて生まれるため、実行前に
    操作主体を解決できない。リクエストのスコープではなく専用の Unit of Work から
    呼ばれるので、本人特定を要求する保存前の境界は掛からない。

    本人は**招待に書かれた本人**である。外部の認証基盤は自分が発行した主体しか
    知らないので、受諾者が名乗る本人IDを受け取る形にはできない。
    """

    def __init__(
        self,
        repositories: IdentityRepositories,
        staff: StaffRepository,
        stores: StoreRepository,
        corporates: CorporateRepository,
        clock: Clock,
        unit_of_work: UnitOfWork,
        lock: OrganizationLock,
    ) -> None:
        self._repositories = repositories
        self._staff = staff
        self._stores = stores
        self._corporates = corporates
        self._clock = clock
        self._unit_of_work = unit_of_work
        self._lock = lock

    async def execute(self, secret: str, subject: VerifiedSubject) -> AccountDto:
        """招待に書かれた本人へ、検証済みの外部主体を一度だけ結び付ける。"""
        self._unit_of_work.ensure_active()
        await self._lock.acquire("identity")
        invitation = await self._repositories.invitations.find_by_digest(
            InvitationDigest(sha256(secret.encode()).hexdigest())
        )
        if invitation is None:
            raise IdentityConflictError("この招待は利用できません。")
        accepted = invitation.accept(now=self._clock.now())
        await self._lock.acquire(f"corporate:{invitation.corporate_id.value}")
        corporate = await self._corporates.get(invitation.corporate_id)
        if corporate is None or not corporate.is_active:
            raise IdentityConflictError("招待先の法人は利用できません。")
        if await self._repositories.people.get(invitation.person_id) is None:
            raise IdentityConflictError("招待された本人を確認できません。")
        await validate_membership_target(
            person_id=invitation.person_id,
            corporate_id=invitation.corporate_id,
            role=invitation.role,
            store_ids=invitation.store_ids,
            staff_id=invitation.staff_id,
            staff=self._staff,
            stores=self._stores,
            links=self._repositories.links,
        )
        account = await self._bind_account(
            person_id=invitation.person_id, subject=subject
        )
        membership = await self._grant_membership(account, invitation)
        await self._repositories.accounts.save(account)
        await self._repositories.memberships.save(membership)
        await self._repositories.invitations.save(accepted)
        return AccountDto.from_entity(account)

    async def _bind_account(
        self, *, person_id: AccountPersonId, subject: VerifiedSubject
    ) -> UserAccount:
        """確認済みの外部主体を、招待された本人のアカウントへ結び付ける。

        本人の照合が招待側へ移った分、ここが「招待の秘密だけでは他人になれない」
        ことを担保する。提示された主体が既に別の本人のものであれば、秘密が正しくても
        受諾は成立しない。
        """
        key = ExternalSubjectKey(subject.principal_id)
        bound = await self._repositories.accounts.get_by_subject(key)
        if bound is not None and bound.person_id != person_id:
            raise IdentityConflictError("外部主体は別の本人に対応しています。")
        account = await self._repositories.accounts.get_by_person(person_id)
        if account is None:
            return UserAccount(
                id=UserAccountId.generate(),
                person_id=person_id,
                external_subject=key,
            )
        if account.status != AccountStatus.ACTIVE or (
            account.external_subject is not None and account.external_subject != key
        ):
            raise IdentityConflictError(
                "この個人アカウントは招待の受諾に利用できません。"
            )
        return replace(account, external_subject=key)

    async def _grant_membership(
        self, account: UserAccount, invitation: UserInvitation
    ) -> CorporateMembership:
        """同じ法人に停止済みの権限があれば、その行を作り直さず再利用する。"""
        if (
            await self._repositories.memberships.find_active_for_account(account.id)
            is not None
        ):
            raise IdentityConflictError("既に有効な法人アクセス権があります。")
        previous = next(
            (
                item
                for item in await self._repositories.memberships.list_by_corporate(
                    invitation.corporate_id
                )
                if item.account_id == account.id
            ),
            None,
        )
        return CorporateMembership(
            id=previous.id if previous else CorporateMembershipId.generate(),
            account_id=account.id,
            corporate_id=invitation.corporate_id,
            role=invitation.role,
            store_ids=invitation.store_ids,
            staff_id=invitation.staff_id,
        )


__all__ = ["AcceptInvitationUseCase"]
