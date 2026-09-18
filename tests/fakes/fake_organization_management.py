"""管理UseCaseの業務検証用境界。原子性や並行実行は証明しない。"""

from app.application.common.organization_lock import OrganizationLock
from app.application.store.management import StoreWorkBoundary
from app.domain.corporate.primitives import CorporateId
from app.domain.store.primitives import StoreId


class FakeOrganizationLock(OrganizationLock):
    """ロック要求の順序を記録する。"""

    def __init__(self) -> None:
        self.keys: list[str] = []

    async def acquire(self, key: str) -> None:
        self.keys.append(key)


class FakeStoreWorkBoundary(StoreWorkBoundary):
    """未完了業務の有無を明示的に与える。"""

    def __init__(self, unfinished: bool = False) -> None:
        self.unfinished = unfinished

    async def has_unfinished(
        self, corporate_id: CorporateId, store_id: StoreId
    ) -> bool:
        return self.unfinished
