"""外部主体に対応するアカウント・本人・所属の保存値だけを取得する。"""

from app.application.identity.interfaces.resolve_actor_query_reader import (
    ResolveActorQueryReader,
)
from app.application.identity.queries.dtos.identity_resolution import (
    IdentityResolutionSnapshot,
    MembershipIdentitySnapshot,
)
from app.domain.identity.primitives import ExternalSubjectKey
from app.domain.identity.repositories import (
    AccountPersonRepository,
    CorporateMembershipRepository,
    UserAccountRepository,
)


class ResolveActorProjection(ResolveActorQueryReader):
    """利用状態やロールを判断せず、Applicationへ参照事実を渡す。"""

    def __init__(
        self,
        people: AccountPersonRepository,
        accounts: UserAccountRepository,
        memberships: CorporateMembershipRepository,
    ) -> None:
        self._people = people
        self._accounts = accounts
        self._memberships = memberships

    async def get_by_subject(
        self, subject: ExternalSubjectKey
    ) -> IdentityResolutionSnapshot | None:
        """主体からアカウントを引き、欠落を含む関連情報を不変の投影で返す。"""
        account = await self._accounts.get_by_subject(subject)
        if account is None:
            return None
        person = await self._people.get(account.person_id)
        membership = await self._memberships.find_active_for_account(account.id)
        membership_snapshot = (
            MembershipIdentitySnapshot(
                id=membership.id,
                account_id=membership.account_id,
                corporate_id=membership.corporate_id,
                status=membership.status,
                role=membership.role,
                staff_id=membership.staff_id,
                store_ids=membership.store_ids,
            )
            if membership is not None
            else None
        )
        return IdentityResolutionSnapshot(
            account_id=account.id,
            account_person_id=account.person_id,
            person_id=person.id if person is not None else None,
            external_subject=account.external_subject,
            account_status=account.status,
            is_vendor_admin=account.is_vendor_admin,
            membership=membership_snapshot,
        )
