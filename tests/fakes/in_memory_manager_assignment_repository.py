"""管理薬剤師の期間競合を検証するインメモリ保存。"""

from app.domain.corporate.primitives import CorporateId
from app.domain.staff.primitives import StaffId
from app.domain.store.manager_assignment import (
    ManagerAssignmentStatus,
    StoreManagerAssignment,
    StoreManagerAssignmentId,
)
from app.domain.store.manager_repository import (
    ManagerAssignmentConflictError,
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

    async def save(self, assignment: StoreManagerAssignment) -> None:
        if assignment.status == ManagerAssignmentStatus.CONFIRMED:
            for existing in self.items.values():
                if (
                    existing.id == assignment.id
                    or existing.status == ManagerAssignmentStatus.CANCELLED
                ):
                    continue
                same_target = (
                    existing.store_id == assignment.store_id
                    or existing.staff_id == assignment.staff_id
                )
                left = existing.period
                right = assignment.period
                overlap = (
                    left.ends_on is None or right.starts_on <= left.ends_on
                ) and (right.ends_on is None or left.starts_on <= right.ends_on)
                if same_target and overlap:
                    raise ManagerAssignmentConflictError(
                        "店舗またはスタッフの任命期間が重複しています。"
                    )
        self.items[assignment.id] = assignment
