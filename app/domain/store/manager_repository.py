"""管理薬剤師の任命履歴と期間競合の保存契約。"""

from datetime import date
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


class ManagerExclusiveDutyConflictError(DomainError):
    """同一人物が、同じ期間に複数の薬局の管理薬剤師を兼ねようとしている。

    薬機法第7条第3項は管理薬剤師の専任を求める。競合相手が別法人にありうる
    ため、メッセージには相手の法人も店舗も含めない（テナントを越えて存在を
    知らせることになる）。
    """

    default_code = "MANAGER_EXCLUSIVE_DUTY_CONFLICT"


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

    async def find_effective(
        self, corporate_id: CorporateId, store_id: StoreId, as_of: date
    ) -> StoreManagerAssignment | None:
        """適用日に有効な確定任命を返す。他法人・未存在は ``None`` で隠す。

        同一店舗で期間が重なる確定任命は排他制約が拒否するので、戻り値は高々
        1件に定まる。在任の有無は臨床集約を保存するたびに問われるため、履歴を
        全件読んでから絞る形にはしない（任命履歴は店舗の年数とともに増える
        一方で、判定に要るのは常に1件である）。
        """
        ...

    async def save(self, assignment: StoreManagerAssignment) -> None:
        """自分以外の確定任命との閉区間重複を原子的に拒否して保存する。"""
        ...
