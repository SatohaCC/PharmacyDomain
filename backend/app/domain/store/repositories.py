"""storeの保存・情報取得の抽象契約。"""

from __future__ import annotations

from datetime import date
from typing import Protocol

from app.domain.corporate.identifiers import CorporateId
from app.domain.staff.identifiers import StaffId
from app.domain.store.entities import Store, StoreManagerAssignment
from app.domain.store.identifiers import StoreId, StoreManagerAssignmentId
from app.domain.store.primitives import InsurancePharmacyNumber, StoreCode, StoreName


class StoreManagerAssignmentRepository(Protocol):
    """取消履歴を保持し、店舗とスタッフ双方の重複を原子的に拒否する。"""

    async def get(
        self, assignment_id: StoreManagerAssignmentId
    ) -> StoreManagerAssignment | None:
        """任命IDで履歴を取得する。"""
        ...

    async def list_by_store(
        self, corporate_id: CorporateId, store_id: StoreId
    ) -> list[StoreManagerAssignment]:
        """対象法人・店舗の取消済みを含む任命を返す。"""
        ...

    async def list_by_staff(
        self, corporate_id: CorporateId, staff_id: StaffId
    ) -> list[StoreManagerAssignment]:
        """対象法人・スタッフの取消済みを含む任命を返す。"""
        ...

    async def find_effective(
        self, corporate_id: CorporateId, store_id: StoreId, as_of: date
    ) -> StoreManagerAssignment | None:
        """適用日に有効な確定任命を返す。他法人・未存在は ``None`` で隠す。

        同一店舗で期間が重なる確定任命は排他制約が拒否するので、戻り値は高々
        1件に定まる。在任の有無は臨床集約を保存するたびに問われるため、履歴を
        全件読んでから絞る形にはしない（任命履歴は店舗の年数とともに増える
        一方で、判定に要るのは常に1件である）。
        """
        ...

    async def save(self, assignment: StoreManagerAssignment) -> None:
        """自分以外の確定任命との閉区間重複を原子的に拒否して保存する。"""
        ...


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
