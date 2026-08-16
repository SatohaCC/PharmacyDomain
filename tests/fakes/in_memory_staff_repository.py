from __future__ import annotations

import copy

from app.domain.corporate import CorporateId
from app.domain.staff import (
    Staff,
    StaffCatalogRepository,
    StaffCode,
    StaffCodeAlreadyExistsError,
    StaffId,
    StaffRepository,
)


class InMemoryStaffRepository(StaffRepository, StaffCatalogRepository):
    """テスト用のインメモリスタッフリポジトリ。"""

    def __init__(self) -> None:
        self.items: dict[StaffId, Staff] = {}
        self.save_count = 0

    async def get(
        self,
        *,
        corporate_id: CorporateId,
        staff_id: StaffId,
    ) -> Staff | None:
        item = self.items.get(staff_id)
        if item is None or item.corporate_id != corporate_id:
            # 他法人のデータまたは存在しない場合は None を返す（境界保護）
            return None
        return copy.deepcopy(item)

    async def save(self, staff: Staff) -> None:
        self.save_count += 1

        if staff.code is not None and await self.exists_by_code(
            corporate_id=staff.corporate_id,
            code=staff.code,
            excluding_id=staff.id,
        ):
            raise StaffCodeAlreadyExistsError(
                f"同一法人内にスタッフコード '{staff.code.value}' は既に登録されています。"
            )

        self.items[staff.id] = copy.deepcopy(staff)

    async def exists_by_code(
        self,
        *,
        corporate_id: CorporateId,
        code: StaffCode,
        excluding_id: StaffId | None = None,
    ) -> bool:
        return any(
            item.corporate_id == corporate_id
            and item.code == code
            and item.id != excluding_id
            for item in self.items.values()
        )

    async def list_by_corporate_id(self, corporate_id: CorporateId) -> list[Staff]:
        return [
            copy.deepcopy(item)
            for item in self.items.values()
            if item.corporate_id == corporate_id
        ]

    async def list_all(self) -> list[Staff]:
        return [copy.deepcopy(item) for item in self.items.values()]
