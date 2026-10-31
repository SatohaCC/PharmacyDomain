"""スタッフ作成時の一括アカウント生成アダプタ。"""

from __future__ import annotations

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
