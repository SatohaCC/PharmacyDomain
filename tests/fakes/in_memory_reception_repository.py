"""受付集約のテスト用Repository。"""

from __future__ import annotations

import copy

from app.domain.corporate.primitives import CorporateId
from app.domain.reception.primitives import ReceptionId
from app.domain.reception.reception import Reception
from app.domain.reception.repository import ReceptionRepository
from app.domain.store.primitives import StoreId


class InMemoryReceptionRepository(ReceptionRepository):
    """法人・店舗境界を適用する受付Repository Fake。"""

    def __init__(self) -> None:
        self.items: dict[tuple[CorporateId, StoreId, ReceptionId], Reception] = {}

    async def get(
        self,
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
        reception_id: ReceptionId,
    ) -> Reception | None:
        """法人・店舗・受付IDが一致する受付だけを返す。"""
        item = self.items.get((corporate_id, store_id, reception_id))
        return copy.deepcopy(item) if item is not None else None

    async def save(self, reception: Reception) -> None:
        """受付を保存する。"""
        key = (reception.corporate_id, reception.store_id, reception.id)
        self.items[key] = copy.deepcopy(reception)
