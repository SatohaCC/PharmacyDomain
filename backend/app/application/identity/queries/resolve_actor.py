"""外部主体に対応する参照事実を照合し、利用可能な操作者を構築する。"""

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


class ResolveActorUseCase:
    """アカウント・本人・所属の有効性と、発行する権限をApplicationで判断する。"""

    def __init__(self, reader: ResolveActorQueryReader) -> None:
        self._reader = reader

    async def execute(self, subject: VerifiedSubject) -> ResolvedActorContext:
        """確認済み外部主体から本人を引き、現在の利用状態を照合する。

        Readerは認可結果を返さない。停止状態・本人の欠落・主体や所属の不一致を
        ここで拒否し、信頼済みActorを生成する責務を永続化実装へ渡さない。
        """
        subject_key = ExternalSubjectKey(subject.principal_id)
        facts = await self._reader.get_by_subject(subject_key)
        if (
            facts is None
            or facts.account_status != AccountStatus.ACTIVE
            or facts.external_subject != subject_key
            or facts.person_id is None
            or facts.person_id != facts.account_person_id
        ):
            raise UnavailableIdentityError()
        if facts.is_vendor_admin:
            return ResolvedActorContext(
                principal_id=subject.principal_id,
                person_id=facts.person_id,
                account_id=facts.account_id,
                roles=frozenset({ActorRole.VENDOR_SYSTEM_ADMIN}),
            )
        membership = facts.membership
        if (
            membership is None
            or membership.status != AccountStatus.ACTIVE
            or membership.account_id != facts.account_id
        ):
            raise UnavailableIdentityError()
        return ResolvedActorContext(
            principal_id=subject.principal_id,
            person_id=facts.person_id,
            account_id=facts.account_id,
            membership_id=membership.id,
            corporate_id=membership.corporate_id,
            roles=frozenset({ActorRole(membership.role.value)}),
            staff_id=membership.staff_id,
            store_ids=membership.store_ids,
        )
