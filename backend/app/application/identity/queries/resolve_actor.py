"""外部主体に対応する参照事実を照合し、利用可能な操作者を構築する。"""

from datetime import date

from app.application.access_control.boundary_models import (
    ActorRole,
    ResolvedActorContext,
)
from app.application.common.clock import Clock, business_date
from app.application.common.exceptions import AuthorizationError
from app.application.identity.boundary_models import VerifiedSubject
from app.application.identity.errors import UnavailableIdentityError
from app.application.identity.interfaces.resolve_actor_query_reader import (
    ResolveActorQueryReader,
)
from app.application.identity.queries.dtos.identity_resolution import (
    IdentityResolutionSnapshot,
    MembershipIdentitySnapshot,
)
from app.application.identity.queries.dtos.identity_views import SelectableStoreDto
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.identity.primitives import AccountStatus, ExternalSubjectKey
from app.domain.store.identifiers import StoreId
from app.domain.store.primitives import ManagerAssignmentStatus


def _resolve_selectable_stores(
    membership: MembershipIdentitySnapshot, applied_on: date
) -> tuple[SelectableStoreDto, ...]:
    """Membership許可店舗と当日有効Staff所属店舗と有効Storeの積集合を返す。"""
    active_membership_stores = membership.store_ids - membership.suspended_store_ids
    if membership.staff_is_active is None:
        return tuple(
            SelectableStoreDto(
                id=str(store_id.value),
                name=str(store_id.value),
                code=None,
            )
            for store_id in sorted(
                active_membership_stores, key=lambda item: item.value
            )
        )
    if not membership.staff_is_active or membership.staff_id is None:
        return ()
    affiliated_store_ids = frozenset(
        item.store_id
        for item in membership.staff_affiliations
        if item.starts_on <= applied_on
        and (item.ends_on is None or applied_on <= item.ends_on)
    )
    candidate_ids = active_membership_stores & affiliated_store_ids
    selectable = [
        SelectableStoreDto(
            id=str(store.id.value),
            name=store.name,
            code=store.code,
        )
        for store in membership.stores
        if store.corporate_id == membership.corporate_id
        and store.is_active
        and store.id in candidate_ids
    ]
    selectable.sort(key=lambda item: item.id)
    return tuple(selectable)


class ResolveActorUseCase:
    """アカウント・本人・所属の有効性と、発行する権限をApplicationで判断する。"""

    def __init__(self, reader: ResolveActorQueryReader, clock: Clock) -> None:
        self._reader = reader
        self._clock = clock

    async def _load_validated_facts(
        self, subject: VerifiedSubject
    ) -> IdentityResolutionSnapshot:
        subject_key = ExternalSubjectKey(subject.principal_id)
        facts = await self._reader.get_by_subject(subject_key)
        if (
            facts is None
            or facts.account_status != AccountStatus.ACTIVE
            or facts.external_subject != subject_key
        ):
            raise UnavailableIdentityError()
        if facts.is_vendor_admin:
            return facts
        if (
            facts.person_id is None
            or facts.account_id is None
            or facts.person_id != facts.account_person_id
        ):
            raise UnavailableIdentityError()
        membership = facts.membership
        if (
            membership is None
            or membership.status != AccountStatus.ACTIVE
            or membership.account_id != facts.account_id
        ):
            raise UnavailableIdentityError()
        return facts

    async def execute(self, subject: VerifiedSubject) -> ResolvedActorContext:
        """確認済み外部主体から本人を引き、現在の利用状態を照合する。

        Readerは認可結果を返さない。停止状態・本人の欠落・主体や所属の不一致を
        ここで拒否し、信頼済みActorを生成する責務を永続化実装へ渡さない。
        """
        facts = await self._load_validated_facts(subject)
        if facts.is_vendor_admin:
            return ResolvedActorContext(
                principal_id=subject.principal_id,
                operator_id=facts.operator_id,
                person_id=facts.person_id,
                account_id=facts.account_id,
                roles=frozenset({ActorRole.VENDOR_SYSTEM_ADMIN}),
            )
        membership = facts.membership
        assert membership is not None
        stores = membership.store_ids - membership.suspended_store_ids
        applied_on = business_date(self._clock)
        managed = frozenset(
            item.store_id
            for item in membership.manager_assignments
            if item.corporate_id == membership.corporate_id
            and item.staff_id == membership.staff_id
            and item.person_id == facts.person_id
            and item.store_id in stores
            and item.status == ManagerAssignmentStatus.CONFIRMED
            and item.starts_on <= applied_on
            and (item.ends_on is None or applied_on <= item.ends_on)
        )
        if managed and (len(managed) != 1 or membership.store_ids != managed):
            raise UnavailableIdentityError()
        selectable_stores = _resolve_selectable_stores(membership, applied_on)
        selectable_ids = frozenset(StoreId.parse(item.id) for item in selectable_stores)
        selected_store_id: StoreId | None = None
        if subject.selected_store_id is not None:
            try:
                selected_store_id = StoreId.parse(subject.selected_store_id)
            except DomainValidationError, ValueError:
                raise AuthorizationError(
                    "選択中の店舗に対する現在の利用権限がありません。"
                ) from None
            if selected_store_id not in selectable_ids:
                raise AuthorizationError(
                    "選択中の店舗に対する現在の利用権限がありません。"
                )
        roles = {ActorRole(membership.role.value)}
        if membership.role.value == ActorRole.CORPORATE_ADMIN.value and stores:
            roles.add(ActorRole.STORE_OPERATOR)
        if managed:
            roles.add(ActorRole.STORE_MANAGER)
        return ResolvedActorContext(
            principal_id=subject.principal_id,
            person_id=facts.person_id,
            account_id=facts.account_id,
            membership_id=membership.id,
            corporate_id=membership.corporate_id,
            roles=frozenset(roles),
            staff_id=membership.staff_id,
            store_ids=stores,
            managed_store_ids=managed,
            selected_store_id=selected_store_id,
            require_store_selection=True,
        )

    async def list_selectable_stores(
        self, subject: VerifiedSubject
    ) -> tuple[SelectableStoreDto, ...]:
        """現在の有効Membership許可店舗と当日Staff所属の積集合を返す。"""
        facts = await self._load_validated_facts(subject)
        if facts.is_vendor_admin or facts.membership is None:
            return ()
        return _resolve_selectable_stores(facts.membership, business_date(self._clock))
