"""所属店舗の勤務条件を適用日付きで追記する。"""

from dataclasses import dataclass
from datetime import date

from app.application.access_control.boundary_models import ActorRole, Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.access_control.policies import AuthorizationService
from app.application.common.clock import Clock, business_date
from app.application.common.exceptions import NotFoundError
from app.application.common.input_normalization import to_optional_text
from app.application.common.organization_lock import OrganizationLock
from app.application.staff.interfaces.work_condition_management import (
    WorkConditionManagement,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.staff.identifiers import StaffId
from app.domain.staff.primitives import (
    StoreDuty,
    WeeklyStoreHours,
    WorkConditionRecorder,
)
from app.domain.staff.repositories import StaffRepository
from app.domain.staff.value_objects import StoreWorkCondition
from app.domain.store.identifiers import StoreId


@dataclass(frozen=True, kw_only=True)
class RecordStoreWorkConditionCommand:
    """一店舗の勤務条件。未登録の週時間数はNoneとする。"""

    corporate_id: str
    staff_id: str
    store_id: str
    effective_from: date
    weekly_hours: str | None
    duty: str


class RecordStoreWorkConditionUseCase:
    """法人管理者または管理対象店舗の管理薬剤師が勤務条件を記録する。"""

    def __init__(
        self,
        repository: StaffRepository,
        access: CorporateAccessBoundary,
        lock: OrganizationLock,
        clock: Clock,
        management: WorkConditionManagement,
    ) -> None:
        self._repository = repository
        self._access = access
        self._lock = lock
        self._clock = clock
        self._management = management

    async def execute(self, command: RecordStoreWorkConditionCommand) -> None:
        corporate = CorporateId.parse(command.corporate_id)
        store = StoreId.parse(command.store_id)
        await self._lock.acquire(f"corporate:{corporate.value}")
        await self._management.require_current(corporate, store)
        actor = self._access.actor
        administrator = bool(
            actor.roles & {ActorRole.VENDOR_SYSTEM_ADMIN, ActorRole.CORPORATE_ADMIN}
        )
        permission = (
            Permission.MANAGE_STAFF if administrator else Permission.MANAGE_STORE_USERS
        )
        await self._access.require_active(corporate_id=corporate, permission=permission)
        AuthorizationService(actor).require_store(
            permission=permission, target_corporate_id=corporate, target_store_id=store
        )
        staff = await self._repository.get(
            corporate_id=corporate, staff_id=StaffId.parse(command.staff_id)
        )
        if staff is None:
            raise NotFoundError()
        try:
            duty = StoreDuty(command.duty)
        except ValueError as error:
            raise DomainValidationError(
                "従事区分は薬剤師・登録販売者・その他から指定してください。"
            ) from error
        raw_hours = to_optional_text(command.weekly_hours)
        updated = staff.record_work_conditions(
            (
                StoreWorkCondition(
                    store_id=store,
                    effective_from=command.effective_from,
                    weekly_hours=WeeklyStoreHours.parse(raw_hours)
                    if raw_hours is not None
                    else None,
                    duty=duty,
                    recorded_at=self._clock.now(),
                    recorded_by=WorkConditionRecorder(actor.principal_id),
                ),
            ),
            applied_on=business_date(self._clock),
        )
        await self._repository.save(updated)
