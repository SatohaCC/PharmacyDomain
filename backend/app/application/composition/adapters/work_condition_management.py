"""勤務条件の変更権限をロック取得後の保存済み事実で再確認する。"""

from app.application.access_control.boundary_models import (
    ActorContext,
    ActorRole,
    ResolvedActorContext,
)
from app.application.common.clock import Clock, business_date
from app.application.common.exceptions import AuthorizationError
from app.application.staff.interfaces.work_condition_management import (
    WorkConditionManagement,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.identity.primitives import AccountStatus, MembershipRole
from app.domain.identity.repositories import (
    CorporateMembershipRepository,
    UserAccountRepository,
)
from app.domain.staff.repositories import StaffRepository
from app.domain.store.identifiers import StoreId
from app.domain.store.repositories import StoreManagerAssignmentRepository


class WorkConditionManagementGuard(WorkConditionManagement):
    def __init__(
        self,
        actor: ActorContext,
        accounts: UserAccountRepository,
        memberships: CorporateMembershipRepository,
        staff: StaffRepository,
        managers: StoreManagerAssignmentRepository,
        clock: Clock,
    ) -> None:
        self._actor = actor
        self._accounts = accounts
        self._memberships = memberships
        self._staff = staff
        self._managers = managers
        self._clock = clock

    async def require_current(
        self, corporate_id: CorporateId, store_id: StoreId
    ) -> None:
        actor = self._actor
        if ActorRole.VENDOR_SYSTEM_ADMIN in actor.roles:
            return
        if (
            not isinstance(actor, ResolvedActorContext)
            or actor.account_id is None
            or actor.membership_id is None
        ):
            raise AuthorizationError(
                "勤務条件の変更には有効な本人とアカウントが必要です。"
            )
        account = await self._accounts.get(actor.account_id)
        membership = await self._memberships.get(actor.membership_id)
        if (
            account is None
            or account.status is not AccountStatus.ACTIVE
            or account.person_id != actor.person_id
            or membership is None
            or membership.status is not AccountStatus.ACTIVE
            or membership.corporate_id != corporate_id
            or membership.account_id != account.id
        ):
            raise AuthorizationError("勤務条件を変更する現在の利用権限がありません。")
        if membership.role is MembershipRole.CORPORATE_ADMIN:
            return
        appointment = await self._managers.find_effective(
            corporate_id, store_id, business_date(self._clock)
        )
        staff = (
            await self._staff.get(corporate_id=corporate_id, staff_id=actor.staff_id)
            if actor.staff_id
            else None
        )
        if (
            appointment is None
            or appointment.staff_id != actor.staff_id
            or appointment.person_id != actor.person_id
            or staff is None
            or not staff.is_active
            or membership.staff_id != actor.staff_id
            or store_id not in membership.active_store_ids
        ):
            raise AuthorizationError(
                "勤務条件の変更には管理対象店舗の有効な任命が必要です。"
            )
