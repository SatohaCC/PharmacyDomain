"""認証基盤から信頼済み ``ActorContext`` を受け取る窓口。

``ActorContext`` をHTTP入力から組み立ててはならない。クライアントが名乗った
法人IDやロールをそのまま信じると、テナント境界がリクエストボディ1つで破れる。
そのためこのProtocolが受け取るのはBearerトークンだけで、それを検証して主体を
決めるのは実装側の責務とする。
"""

from __future__ import annotations

from typing import Protocol

from app.application.access_control import ActorContext
from app.presentational.exceptions import AuthenticationError


class ActorContextProvider(Protocol):
    """資格情報を検証し、信頼済みの操作主体を返す境界。"""

    async def authenticate(self, credential: str | None) -> ActorContext:
        """Bearerトークンから操作主体を決める。

        Args:
            credential: ``Authorization: Bearer`` のトークン部分。ヘッダが無い、
                または Bearer 方式でない場合は ``None``。

        Returns:
            検証済みの操作主体。

        Raises:
            AuthenticationError: 資格情報が無い、または検証できない場合。
                主体を特定できないことは常に失敗であり、匿名の主体を作らない。
        """
        ...


class UnconfiguredActorContextProvider(ActorContextProvider):
    """認証基盤が未接続のとき、業務操作をすべて拒否する既定実装。

    未接続を「誰でもベンダーシステム管理者」に倒すと、開発用の設定のまま本番へ
    出た瞬間に全法人のデータが誰でも読み書きできる。既定は必ず失敗させ、
    認証基盤を接続して初めて業務操作が通るようにする。
    """

    async def authenticate(self, credential: str | None) -> ActorContext:
        """資格情報の内容によらず認証失敗として扱う。"""
        del credential
        raise AuthenticationError("認証基盤が接続されていません。")


__all__ = [
    "ActorContextProvider",
    "UnconfiguredActorContextProvider",
]
