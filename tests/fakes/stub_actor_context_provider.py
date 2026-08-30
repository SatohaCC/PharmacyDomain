"""決め打ちのトークンだけを通す認証基盤のフェイク。"""

from __future__ import annotations

from app.application.access_control import ActorContext
from app.presentational.authentication import ActorContextProvider
from app.presentational.exceptions import AuthenticationError

#: このフェイクが受け付ける唯一のトークン。``Authorization: Bearer`` の値部分。
VALID_TOKEN = "test-actor"


class StubActorContextProvider(ActorContextProvider):
    """トークンが一致したときだけ、あらかじめ決めた操作主体を返す。"""

    def __init__(self, actor: ActorContext) -> None:
        self._actor = actor

    async def authenticate(self, credential: str | None) -> ActorContext:
        """トークンを照合し、一致しなければ認証失敗にする。"""
        if credential != VALID_TOKEN:
            raise AuthenticationError()
        return self._actor
