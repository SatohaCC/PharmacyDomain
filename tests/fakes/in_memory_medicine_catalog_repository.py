"""医薬品マスタRepositoryのインメモリ実装。

**法人IDを取らない。** 薬価基準は国が定めるので法人ごとに内容が違わない。
"""

from __future__ import annotations

import copy
from datetime import date

from app.domain.medicine_catalog.medicine import Medicine
from app.domain.medicine_catalog.primitives import MedicineCatalogEntryId
from app.domain.medicine_catalog.repository import MedicineCatalogRepository
from app.domain.medicine_catalog.services import (
    MedicineEffectivePeriodConflictService,
)
from app.domain.shared.medicine import MedicineIdentifier


class InMemoryMedicineCatalogRepository(MedicineCatalogRepository):
    """テスト用医薬品マスタRepository。"""

    def __init__(self) -> None:
        self.items: dict[MedicineCatalogEntryId, Medicine] = {}

    async def get(self, entry_id: MedicineCatalogEntryId) -> Medicine | None:
        """マスタ行を識別子で取得する。"""
        item = self.items.get(entry_id)
        return copy.deepcopy(item) if item is not None else None

    async def find_effective(
        self,
        *,
        identifier: MedicineIdentifier,
        as_of: date,
    ) -> Medicine | None:
        """指定日に有効なマスタ行を返す。

        期間が重なる行は ``save()`` の契約により存在しないので、
        最初に見つかった1件が答えになる。
        """
        for item in self.items.values():
            if item.identifier == identifier and item.is_effective_on(as_of):
                return copy.deepcopy(item)
        return None

    async def list_versions(self, identifier: MedicineIdentifier) -> list[Medicine]:
        """同じ薬品コードの全ての行を収載日の昇順で返す。"""
        matched = [
            copy.deepcopy(item)
            for item in self.items.values()
            if item.identifier == identifier
        ]
        return sorted(matched, key=lambda item: item.effective_period.listed_on.value)

    async def save(self, medicine: Medicine) -> None:
        """同一薬品コードの収載期間の重複を原子的に拒否して保存する。

        判定は ``MedicineEffectivePeriodConflictService`` を呼び、規則の実装が
        2箇所に分かれないようにする。
        """
        MedicineEffectivePeriodConflictService().ensure_no_conflict(
            medicine,
            [item for item in self.items.values() if item.id != medicine.id],
        )
        self.items[medicine.id] = copy.deepcopy(medicine)
