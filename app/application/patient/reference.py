"""Patient Applicationが依存する外部参照境界。"""

from __future__ import annotations

from typing import Protocol

from app.domain.corporate.primitives import CorporateId
from app.domain.store.primitives import StoreId


class PatientStoreReferenceBoundary(Protocol):
    """店舗集約を保持せず、法人との所属整合だけを確認する境界。"""

    async def require_exists(
        self,
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
    ) -> None:
        """指定法人内に店舗が存在することを確認する。

        Raises:
            PatientStoreNotFoundError: 店舗が存在しないか別法人に所属する。
        """
        ...
