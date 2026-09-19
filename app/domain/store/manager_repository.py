"""管理薬剤師の任命履歴と期間競合の保存契約。"""

from typing import Protocol

from app.domain.corporate.primitives import CorporateId
from app.domain.foundation.exceptions import DomainError
from app.domain.staff.primitives import StaffId
from app.domain.store.manager_assignment import (
    StoreManagerAssignment,
    StoreManagerAssignmentId,
)
from app.domain.store.primitives import StoreId


class ManagerAssignmentConflictError(DomainError):
    """同店舗または同スタッフの任命期間が重複している。"""

    default_code = "MANAGER_ASSIGNMENT_CONFLICT"


class StoreManagerAssignmentRepository(Protocol):
    """取消履歴を保持し、店舗とスタッフ双方の重複を原子的に拒否する。"""

    async def get(
        self, assignment_id: StoreManagerAssignmentId
    ) -> StoreManagerAssignment | None:
        """任命IDで履歴を取得する。"""
        ...

    async def list_by_store(
        self, corporate_id: CorporateId, store_id: StoreId
    ) -> list[StoreManagerAssignment]:
        """対象法人・店舗の取消済みを含む任命を返す。"""
        ...

    async def list_by_staff(
        self, corporate_id: CorporateId, staff_id: StaffId
    ) -> list[StoreManagerAssignment]:
        """対象法人・スタッフの取消済みを含む任命を返す。"""
        ...

    async def save(self, assignment: StoreManagerAssignment) -> None:
        """自分以外の確定任命との閉区間重複を原子的に拒否して保存する。"""
        ...
