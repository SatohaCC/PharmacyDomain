"""法人のリポジトリインターフェース。"""

from __future__ import annotations

from typing import Protocol

from app.domain.corporate.corporate import Corporate
from app.domain.corporate.primitives import CorporateId, CorporateName


class CorporateRepository(Protocol):
    """法人を扱うユースケースが必要とする永続化操作。"""

    async def get(self, corporate_id: CorporateId) -> Corporate | None:
        """指定されたIDの法人を検索して返す。"""
        ...

    async def save(self, corporate: Corporate) -> None:
        """法人を新規登録または変更する。

        同名の別法人が存在する場合は、永続化層の一意性制約と合わせて保存を拒否すること。

        読み込みから保存までの間に同じ集約が別トランザクションで更新されて
        いた場合、上書きせずに ``ConcurrentModificationError`` を送出する。
        同時更新が起こりえない実装（インメモリなど）では送出されない。
        """
        ...

    async def exists_by_name(
        self,
        name: CorporateName,
        *,
        excluding_id: CorporateId | None = None,
    ) -> bool:
        """指定された法人名が既に登録されているか確認する。"""
        ...


# システム起動時・特権バッチ用のリポジトリ
class CorporateCatalogRepository(Protocol):
    async def list_all(self) -> list[Corporate]:
        """全ての法人を返す。

        法人ごとに持つマスタ（記載区分など）を起動時に補完する用途に限る。
        リクエスト経路から呼ぶとテナント境界を越えるので使わないこと。
        """
        ...
