"""店舗別勤務条件を同じトランザクションで変更する境界。"""

from typing import Protocol

from app.application.identity.boundary_models import StoreWorkConditionChange
from app.domain.corporate.identifiers import CorporateId
from app.domain.staff.identifiers import StaffId


class StaffStoreSettingsBoundary(Protocol):
    async def apply(
        self,
        corporate_id: CorporateId,
        staff_id: StaffId,
        changes: tuple[StoreWorkConditionChange, ...],
    ) -> None:
        """所属・資格・現在の変更権限を検証して勤務条件を保存する。"""
        ...
