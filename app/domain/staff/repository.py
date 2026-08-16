"""スタッフのリポジトリインターフェース。"""

from __future__ import annotations

from typing import Protocol

from app.domain.corporate.primitives import CorporateId
from app.domain.staff.primitives import StaffCode, StaffId
from app.domain.staff.staff import Staff


class StaffRepository(Protocol):
    """スタッフ集約を永続化・再構築するための操作インターフェース。"""

    async def get(
        self,
        *,
        corporate_id: CorporateId,
        staff_id: StaffId,
    ) -> Staff | None:
        """指定された法人内の指定されたIDのスタッフを取得する。

        指定された corporate_id とスタッフの corporate_id が一致しない場合
        （他法人のデータ）は None を返すこと。
        """
        ...

    async def save(self, staff: Staff) -> None:
        """スタッフを新規登録または更新する。

        実装側では、同一法人内のスタッフコード（未設定を除く）の一意性制約を
        満たすこと。``corporate_id`` に法人への外部キー制約を張ることも、
        永続化層の責務とする。
        """
        ...

    async def exists_by_code(
        self,
        *,
        corporate_id: CorporateId,
        code: StaffCode,
        excluding_id: StaffId | None = None,
    ) -> bool:
        """同一法人内で指定されたスタッフコードが登録済みか確認する。"""
        ...


class StaffCatalogRepository(Protocol):
    """スタッフの一覧取得など、参照系ユースケースの操作インターフェース。"""

    async def list_by_corporate_id(self, corporate_id: CorporateId) -> list[Staff]:
        """指定された法人に所属するスタッフ一覧を取得する。"""
        ...

    async def list_all(self) -> list[Staff]:
        """システム全体のスタッフ一覧を取得する（システム管理者用）。"""
        ...
