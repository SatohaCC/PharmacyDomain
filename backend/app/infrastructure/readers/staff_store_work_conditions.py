"""スタッフの所属履歴から店舗で絞った参照値を作る。"""

from datetime import date

from app.application.common.exceptions import NotFoundError
from app.application.staff.interfaces.store_work_conditions_reader import (
    StoreWorkConditionsReader,
)
from app.application.staff.queries.dtos.store_work_conditions import (
    StoreStaffAffiliationDto,
    StoreWorkConditionDto,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.staff.identifiers import StaffId
from app.domain.staff.repositories import StaffRepository
from app.domain.staff.value_objects import StoreWorkCondition
from app.domain.store.identifiers import StoreId
from app.domain.store.repositories import StoreManagerAssignmentRepository


def _condition(item: StoreWorkCondition) -> StoreWorkConditionDto:
    return StoreWorkConditionDto(
        effective_from=item.effective_from,
        weekly_hours=str(item.weekly_hours.value)
        if item.weekly_hours is not None
        else None,
        duty=item.duty.value,
        recorded_at=item.recorded_at,
        recorded_by=item.recorded_by.value,
    )


class StoreWorkConditionsProjection(StoreWorkConditionsReader):
    def __init__(
        self, repository: StaffRepository, managers: StoreManagerAssignmentRepository
    ) -> None:
        self._repository = repository
        self._managers = managers

    async def read(
        self,
        *,
        corporate_id: CorporateId,
        staff_id: StaffId,
        store_id: StoreId | None,
        applied_on: date,
    ) -> tuple[StoreStaffAffiliationDto, ...]:
        staff = await self._repository.get(corporate_id=corporate_id, staff_id=staff_id)
        if staff is None:
            raise NotFoundError()
        appointments = await self._managers.list_by_staff(corporate_id, staff_id)
        result = []
        for affiliation in staff.affiliations:
            if store_id is not None and affiliation.store_id != store_id:
                continue
            current = (
                staff.work_condition_on(affiliation.store_id, applied_on)
                if affiliation.period.is_active_on(applied_on)
                else None
            )
            result.append(
                StoreStaffAffiliationDto(
                    store_id=str(affiliation.store_id.value),
                    starts_on=affiliation.period.start_date,
                    ends_on=affiliation.period.end_date,
                    is_primary=affiliation.is_primary,
                    is_managing_pharmacist=affiliation.period.is_active_on(applied_on)
                    and any(
                        item.store_id == affiliation.store_id
                        and item.is_effective_on(applied_on)
                        for item in appointments
                    ),
                    current=_condition(current) if current else None,
                    history=tuple(
                        _condition(item)
                        for item in staff.work_conditions
                        if item.store_id == affiliation.store_id
                        and affiliation.period.is_active_on(item.effective_from)
                    ),
                )
            )
        return tuple(result)
