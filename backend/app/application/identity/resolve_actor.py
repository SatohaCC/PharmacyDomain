"""検証済みの外部主体から最新の内部アクセス権を解決する。"""

from dataclasses import dataclass

from app.application.access_control.models import ActorRole, ResolvedActorContext
from app.application.common.exceptions import ApplicationError
from app.domain.identity.primitives import AccountStatus, ExternalSubjectKey
from app.domain.identity.repository import (
    AccountPersonRepository,
    CorporateMembershipRepository,
    UserAccountRepository,
)


class UnavailableIdentityError(ApplicationError):
    """本人またはアカウントを利用可能な状態として解決できない。"""

    default_message = "この本人のアカウントは利用できません。"


@dataclass(frozen=True, kw_only=True)
class VerifiedSubject:
    """本人確認基盤が実際に検証できた唯一の事実 —— 発行元を含む外部主体。

    内部の本人IDを持たせてはならない。外部の認証基盤が知っているのは自分が
    発行した主体までで、このシステムの本人IDは知らない。持たせられる形にすると、
    本物の認証基盤には埋められない項目をテストのダブルだけが埋められる状態に
    なり、その経路は本番で一度も実行されない。
    """

    principal_id: str


class ResolveActorUseCase:
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

    async def execute(self, subject: VerifiedSubject) -> ResolvedActorContext:
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
        # 監査の追記は本人とアカウントの両方を要求する。アカウントから本人へ
        # たどる順序になったので、本人の行が消えている状態をここで止める。
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
