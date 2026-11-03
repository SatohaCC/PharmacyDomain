"""店舗に限定した所属・勤務条件の読取能力。"""

from datetime import date
from typing import Protocol

from app.application.staff.queries.dtos.store_work_conditions import (
    StoreStaffAffiliationDto,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.staff.identifiers import StaffId
from app.domain.store.identifiers import StoreId


class StoreWorkConditionsReader(Protocol):
    async def read(
        self,
        *,
        corporate_id: CorporateId,
        staff_id: StaffId,
        store_id: StoreId | None,
        applied_on: date,
    ) -> tuple[StoreStaffAffiliationDto, ...]:
        """指定された店舗だけの勤務条件を取得する。"""
        ...
