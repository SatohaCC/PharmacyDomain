"""受付のリポジトリインターフェース。"""

from __future__ import annotations

from typing import Protocol

from app.domain.corporate.primitives import CorporateId
from app.domain.reception.primitives import ReceptionId
from app.domain.reception.reception import Reception
from app.domain.store.primitives import StoreId


class ReceptionRepository(Protocol):
    """受付の受信基準と訂正履歴を永続化する境界。"""

    async def get(
        self,
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
        reception_id: ReceptionId,
    ) -> Reception | None:
        """法人・店舗境界を含めて受付を取得する。"""
        ...

    async def save(self, reception: Reception) -> None:
        """受付の受信記録を保存する。"""
        ...
