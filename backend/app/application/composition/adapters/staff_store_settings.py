"""店舗の利用権限変更と勤務条件の更新を同じ保存境界へ接続する。"""

from app.application.common.clock import Clock, business_date
from app.application.common.exceptions import NotFoundError
from app.application.common.input_normalization import to_optional_text
from app.application.identity.boundary_models import StoreWorkConditionChange
from app.application.identity.interfaces.staff_store_settings import (
    StaffStoreSettingsBoundary,
)
from app.application.staff.interfaces.references import StaffStoreReference
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
from app.domain.staff.services import StaffStoreAssignmentService
from app.domain.staff.value_objects import StoreWorkCondition
from app.domain.store.identifiers import StoreId


class StaffStoreSettingsAdapter(StaffStoreSettingsBoundary):
    def __init__(
        self,
        staff: StaffRepository,
        stores: StaffStoreReference,
        clock: Clock,
        management: WorkConditionManagement,
        principal_id: str,
    ) -> None:
        self._staff = staff
        self._stores = stores
        self._clock = clock
        self._management = management
        self._principal_id = principal_id

    async def apply(
        self,
        corporate_id: CorporateId,
        staff_id: StaffId,
        changes: tuple[StoreWorkConditionChange, ...],
    ) -> None:
        staff = await self._staff.get(corporate_id=corporate_id, staff_id=staff_id)
        if staff is None:
            raise NotFoundError()
        records: list[StoreWorkCondition] = []
        for change in changes:
            store_id = StoreId.parse(change.store_id)
            await self._management.require_current(corporate_id, store_id)
            store = await self._stores.get(corporate_id=corporate_id, store_id=store_id)
            if store is None:
                raise NotFoundError("指定された店舗が見つかりません。")
            if not any(
                item.store_id == store_id
                and item.period.is_active_on(change.effective_from)
                for item in staff.affiliations
            ):
                if change.starts_on is None:
                    raise DomainValidationError(
                        "新しく所属する店舗の所属開始日を指定してください。"
                    )
                assignment = StaffStoreAssignmentService()
                if staff.current_home_store_id(change.starts_on) is None:
                    staff = assignment.assign_home_store(staff, store, change.starts_on)
                else:
                    staff = assignment.assign_concurrent_store(
                        staff, store, change.starts_on
                    )
            try:
                duty = StoreDuty(change.duty)
            except ValueError as error:
                raise DomainValidationError(
                    "従事区分は薬剤師・登録販売者・その他から指定してください。"
                ) from error
            raw = to_optional_text(change.weekly_hours)
            hours = WeeklyStoreHours.parse(raw) if raw is not None else None
            current = staff.work_condition_on(store_id, change.effective_from)
            if (
                current is not None
                and current.weekly_hours == hours
                and current.duty == duty
            ):
                continue
            records.append(
                StoreWorkCondition(
                    store_id=store_id,
                    effective_from=change.effective_from,
                    weekly_hours=hours,
                    duty=duty,
                    recorded_at=self._clock.now(),
                    recorded_by=WorkConditionRecorder(self._principal_id),
                )
            )
        staff = staff.record_work_conditions(
            tuple(records), applied_on=business_date(self._clock)
        )
        await self._staff.save(staff)
