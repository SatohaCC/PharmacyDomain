"""Repositoryから参照用DTOを投影するアダプタ。保存は行わない。"""

from app.application.access_control.boundary_models import (
    ActorRole,
    ResolvedActorContext,
)
from app.application.identity.boundary_models import VerifiedSubject
from app.application.identity.errors import UnavailableIdentityError
from app.application.identity.interfaces.resolve_actor_query_reader import (
    ResolveActorQueryReader,
)
from app.domain.identity.primitives import AccountStatus, ExternalSubjectKey
from app.domain.identity.repositories import (
    AccountPersonRepository,
    CorporateMembershipRepository,
    UserAccountRepository,
)


class ResolveActorProjection(ResolveActorQueryReader):
    """停止状態と法人権限を毎回読み直してActorを生成する。"""

    def __init__(
        self,
        people: AccountPersonRepository,
        accounts: UserAccountRepository,
        memberships: CorporateMembershipRepository,
    ) -> None:
        self._people = people
        self._accounts = accounts
        self._memberships = memberships

    async def read(self, subject: VerifiedSubject) -> ResolvedActorContext:
        """外部主体からアカウントと本人を引き、現在有効なアクセス権を照合する。

        出発点を外部主体にしているので、「主体を固定していないアカウント」は
        検索の時点で到達できない。分岐で除外していた頃は、その分岐を書き忘れると
        未固定のアカウントにだけ照合が効かなくなっていた。
        """
        account = await self._accounts.get_by_subject(
            ExternalSubjectKey(subject.principal_id)
        )
        if account is None or account.status != AccountStatus.ACTIVE:
            raise UnavailableIdentityError()
        person = await self._people.get(account.person_id)
        if person is None:
            raise UnavailableIdentityError()
        if account.is_vendor_admin:
            return ResolvedActorContext(
                principal_id=subject.principal_id,
                person_id=person.id,
                account_id=account.id,
                roles=frozenset({ActorRole.VENDOR_SYSTEM_ADMIN}),
            )
        membership = await self._memberships.find_active_for_account(account.id)
        if membership is None:
            raise UnavailableIdentityError()
        return ResolvedActorContext(
            principal_id=subject.principal_id,
            person_id=person.id,
            account_id=account.id,
            membership_id=membership.id,
            corporate_id=membership.corporate_id,
            roles=frozenset({ActorRole(membership.role.value)}),
            staff_id=membership.staff_id,
            store_ids=membership.store_ids,
        )
