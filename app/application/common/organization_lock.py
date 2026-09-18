"""複数集約の管理変更を直列化するトランザクション内の境界。"""

from typing import Protocol


class OrganizationLock(Protocol):
    """キーが同じ更新をトランザクション終了まで直列化する。"""

    async def acquire(self, key: str) -> None:
        """法人または本人の管理変更ロックを取得する。"""
        ...
