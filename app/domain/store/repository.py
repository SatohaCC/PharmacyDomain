"""店舗のリポジトリインターフェース。"""

from __future__ import annotations

from typing import Protocol

from app.domain.corporate.primitives import CorporateId
from app.domain.store.primitives import (
    InsurancePharmacyNumber,
    StoreCode,
    StoreId,
    StoreName,
)
from app.domain.store.store import Store


class StoreRepository(Protocol):
    """店舗の集約（Store）を永続化・再構築するための操作インターフェース。"""

    async def get(self, store_id: StoreId) -> Store | None:
        """指定されたIDの店舗を取得する。"""
        ...

    async def save(self, store: Store) -> None:
        """店舗を新規登録または更新する。

        実装側では、同一法人内の店舗名と店舗コード（未設定を除く）、および
        保険薬局指定番号（未設定を除く）の一意性制約も満たすこと。あわせて
        ``corporate_id`` に法人への外部キー制約を張ること。通常のユースケースでは
        ``CorporateAccessService`` が保存前に法人の実在・有効状態を確認するが、ここでも
        永続化層の外部キー制約を最終的な不整合の防御線とする。
        """
        ...

    async def exists_by_name(
        self,
        *,
        corporate_id: CorporateId,
        name: StoreName,
        excluding_id: StoreId | None = None,
    ) -> bool:
        """同一法人内で指定された店舗名が既に登録されているか確認する。"""
        ...

    async def exists_by_code(
        self,
        *,
        corporate_id: CorporateId,
        code: StoreCode,
        excluding_id: StoreId | None = None,
    ) -> bool:
        """同一法人内で指定された店舗コードが既に登録されているか確認する。"""
        ...

    async def exists_by_insurance_pharmacy_number(
        self,
        *,
        number: InsurancePharmacyNumber,
        excluding_id: StoreId | None = None,
    ) -> bool:
        """指定された保険薬局指定番号が別の店舗に登録されているか確認する。"""
        ...


class StoreCatalogRepository(Protocol):
    """店舗の一覧取得・検索など、参照系ユースケースのための操作インターフェース。"""

    async def list_by_corporate_id(
        self,
        corporate_id: CorporateId,
    ) -> list[Store]:
        """指定された法人に所属する店舗一覧を取得する。"""
        ...

    async def list_all(self) -> list[Store]:
        """システム全体の全店舗を取得する（システム管理者用）。"""
        ...
