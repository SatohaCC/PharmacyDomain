"""法人ロック内で勤務条件の変更者を再確認する能力。"""

from typing import Protocol

from app.domain.corporate.identifiers import CorporateId
from app.domain.store.identifiers import StoreId


class WorkConditionManagement(Protocol):
    async def require_current(
        self, corporate_id: CorporateId, store_id: StoreId
    ) -> None:
        """最新の本人・アカウント・法人管理権限または管理薬剤師の任命を確認する。"""
        ...
