"""管理薬剤師の期間競合を検証するインメモリ保存。"""

from datetime import date

from app.domain.corporate.primitives import CorporateId
from app.domain.staff.primitives import StaffId
from app.domain.store.manager_assignment import (
    ManagerAssignmentStatus,
    StoreManagerAssignment,
    StoreManagerAssignmentId,
)
from app.domain.store.manager_repository import (
    ManagerAssignmentConflictError,
    ManagerExclusiveDutyConflictError,
    StoreManagerAssignmentRepository,
)
from app.domain.store.primitives import StoreId


class InMemoryStoreManagerAssignmentRepository(StoreManagerAssignmentRepository):
    """店舗・スタッフ双方の重複を拒否し、取消履歴は残す。"""

    def __init__(self) -> None:
        self.items: dict[StoreManagerAssignmentId, StoreManagerAssignment] = {}

    async def get(
        self, assignment_id: StoreManagerAssignmentId
    ) -> StoreManagerAssignment | None:
        return self.items.get(assignment_id)

    async def list_by_store(
        self, corporate_id: CorporateId, store_id: StoreId
    ) -> list[StoreManagerAssignment]:
        return [
            item
            for item in self.items.values()
            if item.corporate_id == corporate_id and item.store_id == store_id
        ]

    async def list_by_staff(
        self, corporate_id: CorporateId, staff_id: StaffId
    ) -> list[StoreManagerAssignment]:
        return [
            item
            for item in self.items.values()
            if item.corporate_id == corporate_id and item.staff_id == staff_id
        ]

    async def find_effective(
        self, corporate_id: CorporateId, store_id: StoreId, as_of: date
    ) -> StoreManagerAssignment | None:
        """適用日に有効な確定任命を1件返す。"""
        for item in self.items.values():
            if (
                item.corporate_id == corporate_id
                and item.store_id == store_id
                and item.is_effective_on(as_of)
            ):
                return item
        return None

    async def save(self, assignment: StoreManagerAssignment) -> None:
        """店舗の重複と、人単位の兼務を別の例外として拒否する。

        同じ店舗かつ同じ人物で期間が重なる場合は、実物ではどちらの排他制約が
        報告されるかがサーバ任せになる。ここでは店舗側を先に見る。どちらも409
        なので応答の形は変わらないが、この一点だけは実物と型が揃わないことが
        ありうる。
        """
        if assignment.status == ManagerAssignmentStatus.CONFIRMED:
            for existing in self.items.values():
                if (
                    existing.id == assignment.id
                    or existing.status == ManagerAssignmentStatus.CANCELLED
                ):
                    continue
                left = existing.period
                right = assignment.period
                overlap = (
                    left.ends_on is None or right.starts_on <= left.ends_on
                ) and (right.ends_on is None or left.starts_on <= right.ends_on)
                if not overlap:
                    continue
                if existing.store_id == assignment.store_id:
                    raise ManagerAssignmentConflictError(
                        "その店舗には、同じ期間に別の管理薬剤師の任命があります。"
                    )
                if existing.person_id == assignment.person_id:
                    raise ManagerExclusiveDutyConflictError(
                        "同じ人物が、同じ期間に複数の薬局の管理薬剤師を兼ねることはできません。"
                    )
        self.items[assignment.id] = assignment
