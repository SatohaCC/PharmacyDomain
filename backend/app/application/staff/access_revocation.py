"""退職に伴う法人アクセス権の停止を、スタッフ側から見た境界として表す。"""

from typing import Protocol

from app.domain.staff.staff import Staff


class StaffAccessRevocationBoundary(Protocol):
    """退職したスタッフの法人アクセス権を止める境界。

    スタッフのユースケースは、法人アクセス権の台帳も最後の管理者の規則も知らない。
    実装を直接持つと Identity コンテキストの都合がスタッフ側へ流れ込むので、
    Composition Root で接続する Protocol にだけ依存させる。
    """

    async def revoke_for(self, staff: Staff) -> None:
        """無効化済みのスタッフに対応するアクセス権を停止する。

        有効なスタッフに対しては何もしない（再雇用で権限は復活させない）。

        Raises:
            IdentityConflictError: 最後の有効な法人管理者を失う場合。
        """
        ...


__all__ = ["StaffAccessRevocationBoundary"]
