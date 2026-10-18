"""管理薬剤師任命が必要とするスタッフ参照の抽象。"""

from typing import Protocol

from app.domain.corporate.identifiers import CorporateId
from app.domain.staff.identifiers import StaffId
from app.domain.store.value_objects import ManagerStaffSource


class ManagerStaffReference(Protocol):
    """任命用の資格・所属・同一性だけを返す。"""

    async def get(
        self, *, corporate_id: CorporateId, staff_id: StaffId
    ) -> ManagerStaffSource | None:
        """未存在と別法人はともにNoneへ畳む。"""
        ...
