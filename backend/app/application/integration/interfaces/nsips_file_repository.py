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

    async def reserve(
        self,
        ledger: NsipsFileRecord,
    ) -> NsipsFileRecord | None:
        """ファイル取込を予約する。既に同一操作のエントリが存在すれば既存レコードを返し、新規予約できた場合は None を返す。"""
        ...

    async def save(self, ledger: NsipsFileRecord) -> None:
        """台帳エントリを保存する。"""
        ...

    async def save_failed(self, ledger: NsipsFileRecord) -> None:
        """失敗した台帳エントリを保存する。実装によってはロールバックから独立して確定する。"""
        ...


__all__ = ["NsipsFileRepository"]
