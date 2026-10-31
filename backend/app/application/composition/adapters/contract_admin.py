"""初期管理者アカウント登録アダプタ。"""

from __future__ import annotations

from app.application.composition.interfaces.contract_operations import (
    RegisterContractAdminOperation,
    RegisteredAdminUser,
)
from app.application.identity.boundary_interfaces.local_authentication import (
    CredentialWriter,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.identity.entities import CorporateMembership, UserAccount
from app.domain.identity.identifiers import CorporateMembershipId
from app.domain.identity.primitives import (
    AccountStatus,
    CorporateUserEmail,
    ExternalSubjectKey,
    MembershipRole,
)
from app.domain.identity.repositories import (
    CorporateMembershipRepository,
    UserAccountRepository,
)
from app.domain.shared.actor import AccountPersonId, UserAccountId


class ContractAdminAdapter(RegisterContractAdminOperation):
    """法人契約時に初期管理者のアカウント・メンバーシップ・認証資格情報を保存する。"""

    def __init__(
        self,
        accounts: UserAccountRepository,
        memberships: CorporateMembershipRepository,
        credentials: CredentialWriter,
    ) -> None:
        self._accounts = accounts
        self._memberships = memberships
        self._credentials = credentials

    async def execute(
        self,
        *,
        corporate_id: str,
        person_id: str,
        email: str,
        initial_password: str,
    ) -> RegisteredAdminUser:
        parsed_corporate_id = CorporateId.parse(corporate_id)
        parsed_person_id = AccountPersonId.parse(person_id)

        account_id = UserAccountId.generate()
        subject = f"local:{account_id.value}"
        account = UserAccount(
            id=account_id,
            corporate_id=parsed_corporate_id,
            person_id=parsed_person_id,
            status=AccountStatus.ACTIVE,
            external_subject=ExternalSubjectKey(subject),
        )
        await self._accounts.save(account)

        membership = CorporateMembership(
            id=CorporateMembershipId.generate(),
            account_id=account_id,
            corporate_id=parsed_corporate_id,
            role=MembershipRole.CORPORATE_ADMIN,
            store_ids=frozenset(),
            staff_id=None,
        )
        await self._memberships.save(membership)

        normalized_email = CorporateUserEmail(email).value
        await self._credentials.issue(
            parsed_corporate_id,
            normalized_email,
            initial_password,
            subject,
        )

        return RegisteredAdminUser(
            id=str(account_id.value),
            email=normalized_email,
        )
