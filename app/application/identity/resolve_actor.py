"""検証済みの本人から最新の内部アクセス権を解決する。"""

from dataclasses import dataclass

from app.application.access_control.models import ActorRole, ResolvedActorContext
from app.application.common.exceptions import ApplicationError
from app.domain.identity.primitives import AccountPersonId, AccountStatus
from app.domain.identity.repository import (
    AccountPersonRepository,
    CorporateMembershipRepository,
    UserAccountRepository,
)


class UnavailableIdentityError(ApplicationError):
    """本人またはアカウントを利用可能な状態として解決できない。"""

    default_message = "この本人のアカウントは利用できません。"


@dataclass(frozen=True, kw_only=True)
class VerifiedIdentity:
    """本人確認境界の内側で生成された本人の参照。"""

    person_id: AccountPersonId
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

    async def execute(self, identity: VerifiedIdentity) -> ResolvedActorContext:
        """本人とアカウント、現在有効なアクセス権を照合する。"""
        person = await self._people.get(identity.person_id)
        account = await self._accounts.get_by_person(identity.person_id)
        if person is None or account is None or account.status != AccountStatus.ACTIVE:
            raise UnavailableIdentityError()
        # 外部主体を固定していないアカウントを通すと、この照合が「そのアカウント
        # だけ効かない」形になる。本人IDさえ一致すれば任意の principal_id で
        # ベンダー権限まで発行できてしまうので、未固定そのものを拒否する。
        if (
            account.external_subject is None
            or account.external_subject.value != identity.principal_id
        ):
            raise UnavailableIdentityError()
        if account.is_vendor_admin:
            return ResolvedActorContext(
                principal_id=identity.principal_id,
                person_id=person.id,
                account_id=account.id,
                roles=frozenset({ActorRole.VENDOR_SYSTEM_ADMIN}),
            )
        membership = await self._memberships.find_active_for_account(account.id)
        if membership is None:
            raise UnavailableIdentityError()
        return ResolvedActorContext(
            principal_id=identity.principal_id,
            person_id=person.id,
            account_id=account.id,
            membership_id=membership.id,
            corporate_id=membership.corporate_id,
            roles=frozenset({ActorRole(membership.role.value)}),
            staff_id=membership.staff_id,
            store_ids=membership.store_ids,
        )
