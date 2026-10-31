"""スタッフ作成時の一括アカウント生成アダプタ。"""

from __future__ import annotations

from app.application.access_control.boundary_models import ResolvedActorContext
from app.application.common.exceptions import AuthorizationError
from app.application.identity.boundary_interfaces.local_authentication import (
    CredentialWriter,
)
from app.application.staff.interfaces.account_registration import (
    StaffAccountRegistrationBoundary,
    StaffAccountRegistrationResult,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.identity.entities import (
    AccountPerson,
    CorporateMembership,
    StaffPersonLink,
    UserAccount,
)
from app.domain.identity.identifiers import CorporateMembershipId
from app.domain.identity.primitives import (
    AccountStatus,
    CorporateUserEmail,
    ExternalSubjectKey,
    MembershipRole,
)
from app.domain.identity.repositories import (
    AccountPersonRepository,
    CorporateMembershipRepository,
    StaffPersonLinkRepository,
    UserAccountRepository,
)
from app.domain.shared.actor import AccountPersonId, UserAccountId
from app.domain.shared.person_name import PersonNames
from app.domain.staff.identifiers import StaffId
from app.domain.store.identifiers import StoreId


class StaffAccountRegistrationAdapter(StaffAccountRegistrationBoundary):
    """スタッフ登録と同じUoW内で本人・アカウント・リンク・メンバーシップ・認証資格情報を一括生成する。"""

    def __init__(
        self,
        people: AccountPersonRepository,
        accounts: UserAccountRepository,
        memberships: CorporateMembershipRepository,
        links: StaffPersonLinkRepository,
        credentials: CredentialWriter,
    ) -> None:
        self._people = people
        self._accounts = accounts
        self._memberships = memberships
        self._links = links
        self._credentials = credentials

    async def require_active_actor(
        self,
        *,
        actor: ResolvedActorContext,
        corporate_id: CorporateId,
        store_id: StoreId,
    ) -> None:
        """現在の保存済み状態から、本人と店舗の利用権限を検証する。"""
        account = (
            await self._accounts.get(actor.account_id) if actor.account_id else None
        )
        membership = (
            await self._memberships.get(actor.membership_id)
            if actor.membership_id
            else None
        )
        link = await self._links.get(actor.staff_id) if actor.staff_id else None
        person = await self._people.get(actor.person_id) if actor.person_id else None
        if (
            account is None
            or account.status is not AccountStatus.ACTIVE
            or account.corporate_id != corporate_id
            or account.person_id != actor.person_id
            or membership is None
            or membership.status is not AccountStatus.ACTIVE
            or membership.corporate_id != corporate_id
            or membership.account_id != account.id
            or membership.staff_id != actor.staff_id
            or store_id not in membership.active_store_ids
            or link is None
            or link.corporate_id != corporate_id
            or link.person_id != actor.person_id
            or person is None
            or person.corporate_id != corporate_id
        ):
            raise AuthorizationError(
                "現在有効なアカウント・本人対応・店舗利用権限が必要です。"
            )

    async def register_account(
        self,
        *,
        corporate_id: CorporateId,
        staff_id: StaffId,
        names: PersonNames,
        email: str,
        password: str,
        role: str,
        store_ids: frozenset[StoreId],
    ) -> StaffAccountRegistrationResult:
        normalized_email = CorporateUserEmail(email).value

        person_id = AccountPersonId.generate()
        person = AccountPerson(
            id=person_id,
            corporate_id=corporate_id,
            names=names,
        )
        await self._people.save(person)

        link = StaffPersonLink(
            id=staff_id,
            corporate_id=corporate_id,
            person_id=person_id,
        )
        await self._links.save(link)

        account_id = UserAccountId.generate()
        subject = f"local:{account_id.value}"
        account = UserAccount(
            id=account_id,
            corporate_id=corporate_id,
            person_id=person_id,
            status=AccountStatus.ACTIVE,
            external_subject=ExternalSubjectKey(subject),
        )
        await self._accounts.save(account)

        membership_role = MembershipRole(role)
        membership = CorporateMembership(
            id=CorporateMembershipId.generate(),
            account_id=account_id,
            corporate_id=corporate_id,
            role=membership_role,
            store_ids=store_ids,
            staff_id=staff_id,
        )
        await self._memberships.save(membership)

        await self._credentials.issue(corporate_id, normalized_email, password, subject)

        return StaffAccountRegistrationResult(
            person_id=person_id,
            account_id=account_id,
            membership_id=membership.id,
            email=normalized_email,
        )
