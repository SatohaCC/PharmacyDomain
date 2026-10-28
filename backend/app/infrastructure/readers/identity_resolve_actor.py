"""外部主体に対応するアカウント・本人・所属の保存値だけを取得する。"""

from app.application.identity.interfaces.resolve_actor_query_reader import (
    ResolveActorQueryReader,
)
from app.application.identity.queries.dtos.identity_resolution import (
    IdentityResolutionSnapshot,
    ManagerIdentitySnapshot,
    MembershipIdentitySnapshot,
)
from app.domain.identity.primitives import ExternalSubjectKey
from app.domain.identity.repositories import (
    AccountPersonRepository,
    CorporateMembershipRepository,
    UserAccountRepository,
)
from app.domain.store.repositories import StoreManagerAssignmentRepository


class ResolveActorProjection(ResolveActorQueryReader):
    """利用状態やロールを判断せず、Applicationへ参照事実を渡す。"""

    def __init__(
        self,
        people: AccountPersonRepository,
        accounts: UserAccountRepository,
        memberships: CorporateMembershipRepository,
        managers: StoreManagerAssignmentRepository,
    ) -> None:
        self._people = people
        self._accounts = accounts
        self._memberships = memberships
        self._managers = managers

    async def get_by_subject(
        self, subject: ExternalSubjectKey
    ) -> IdentityResolutionSnapshot | None:
        """主体からアカウントを引き、欠落を含む関連情報を不変の投影で返す。"""
        account = await self._accounts.get_by_subject(subject)
        if account is None:
            return None
        person = await self._people.get(account.person_id)
        membership = await self._memberships.find_active_for_account(account.id)
        assignments = (
            await self._managers.list_by_staff(
                membership.corporate_id, membership.staff_id
            )
            if membership is not None and membership.staff_id is not None
            else []
        )
        membership_snapshot = (
            MembershipIdentitySnapshot(
                id=membership.id,
                account_id=membership.account_id,
                corporate_id=membership.corporate_id,
                status=membership.status,
                role=membership.role,
                staff_id=membership.staff_id,
                store_ids=membership.store_ids,
                suspended_store_ids=membership.suspended_store_ids,
                manager_assignments=tuple(
                    ManagerIdentitySnapshot(
                        corporate_id=item.corporate_id,
                        store_id=item.store_id,
                        staff_id=item.staff_id,
                        person_id=item.person_id,
                        status=item.status,
                        starts_on=item.period.starts_on,
                        ends_on=item.period.ends_on,
                    )
                    for item in assignments
                ),
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
