"""スタッフ配属が必要とする店舗参照の抽象。"""

from typing import Protocol

from app.domain.corporate.identifiers import CorporateId
from app.domain.staff.value_objects import StoreSource
from app.domain.store.identifiers import StoreId


class StaffStoreReference(Protocol):
    """対象法人の店舗事実だけを返す。"""

    async def get(
        self, *, corporate_id: CorporateId, store_id: StoreId
    ) -> StoreSource | None:
        """未存在と別法人はともにNoneへ畳む。"""
        ...
