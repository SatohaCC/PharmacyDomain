"""店舗横断薬歴テスト用の店舗操作Boundary Fake。"""

from app.application.access_control.store_access import (
    StoreOperation,
    StoreOperationBoundary,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.store.primitives import StoreId


class FakeMedicationHistoryStoreOperations(StoreOperationBoundary):
    """検証対象店舗と業務区分を記録し、指定した業務エラーを送出する。"""

    def __init__(self) -> None:
        self.calls: list[tuple[CorporateId, StoreId, StoreOperation]] = []
        self.failures: dict[tuple[CorporateId, StoreId], Exception] = {}

    async def require_allowed(
        self,
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
        operation: StoreOperation,
    ) -> None:
        """店舗と業務を記録し、設定された失敗条件を再現する。"""
        self.calls.append((corporate_id, store_id, operation))
        failure = self.failures.get((corporate_id, store_id))
        if failure is not None:
            raise failure
