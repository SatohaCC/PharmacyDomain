"""NSIPS取込台帳のテスト用Repository。"""

from __future__ import annotations

import copy

from app.application.integration.boundary_models import (
    NsipsFileRecord,
    NsipsFileStatus,
    NsipsOperation,
)
from app.application.integration.interfaces.nsips_file_repository import (
    NsipsFileRepository,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.store.identifiers import StoreId


class InMemoryNsipsFileRepository(NsipsFileRepository):
    """法人・店舗境界を適用するNSIPS取込台帳Repository Fake。"""

    def __init__(self) -> None:
        self.items: dict[
            tuple[CorporateId, StoreId, str, NsipsOperation], NsipsFileRecord
        ] = {}

    async def get_by_identity(
        self,
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
        file_id: str,
        operation: NsipsOperation,
    ) -> NsipsFileRecord | None:
        """同一調剤・同一操作の台帳エントリを取得する。"""
        item = self.items.get((corporate_id, store_id, file_id, operation))
        return copy.deepcopy(item) if item is not None else None

    async def get_applied_by_file_id(
        self,
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
        file_id: str,
    ) -> NsipsFileRecord | None:
        """指定された file_id で適用済みの登録・一括台帳エントリを取得する。"""
        for item in self.items.values():
            if (
                item.corporate_id == corporate_id
                and item.store_id == store_id
                and item.file_id == file_id
                and item.status is NsipsFileStatus.APPLIED
            ):
                return copy.deepcopy(item)
        return None

    async def save(self, ledger: NsipsFileRecord) -> None:
        """台帳エントリを保存する。"""
        key = (
            ledger.corporate_id,
            ledger.store_id,
            ledger.file_id,
            ledger.operation,
        )
        self.items[key] = copy.deepcopy(ledger)


__all__ = ["InMemoryNsipsFileRepository"]
