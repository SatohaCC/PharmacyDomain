"""NSIPS取込台帳のRepository境界。"""

from __future__ import annotations

from typing import Protocol

from app.application.integration.boundary_models import (
    NsipsFileRecord,
    NsipsOperation,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.store.identifiers import StoreId


class NsipsFileRepository(Protocol):
    """NSIPS取込台帳の永続化を担当するRepositoryインターフェース。"""

    async def get_by_identity(
        self,
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
        file_id: str,
        operation: NsipsOperation,
    ) -> NsipsFileRecord | None:
        """同一調剤・同一操作の台帳エントリを取得する。"""
        ...

    async def get_applied_by_file_id(
        self,
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
        file_id: str,
    ) -> NsipsFileRecord | None:
        """指定された file_id で適用済みの登録・一括台帳エントリを取得する。"""
        ...

    async def save(self, ledger: NsipsFileRecord) -> None:
        """台帳エントリを保存する。"""
        ...


__all__ = ["NsipsFileRepository"]
