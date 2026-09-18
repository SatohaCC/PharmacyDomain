"""リクエスト内の全保存に本人特定を要求する境界。"""

from collections.abc import Awaitable, Callable

from app.application.access_control.models import ActorContext, ResolvedActorContext
from app.application.identity.resolve_actor import UnavailableIdentityError


class ResolvedActorWriteGuard:
    """本人とアカウントが特定できていないリクエストの保存を拒否する。

    判定をトランザクションの確定直前へ置いてはならない。FastAPI の yield 依存は
    ``yield`` 以降を**応答を送り終えてから**実行するため、確定直前で例外を出すと、
    クライアントは 201 と採番されたIDを受け取ったあとに黙ってロールバックされる。
    例外は共通の翻訳表にも届かない。

    保存そのものを止めれば、例外はハンドラの実行中に送出され、``errors.py`` の表が
    401 へ写し、トランザクションは通常の失敗経路で破棄される。監査の追記が本人を
    要求する以上、追記できない保存は最初から成立させない。

    本人を確定できない経路（招待の受諾のように、アカウントがその操作で初めて
    生まれる場合）は、リクエストのスコープではなく専用の Unit of Work を使う。
    そちらはこの境界を設定しないので、この規則の対象外である。
    """

    def __init__(
        self,
        actor: ActorContext,
        inner: Callable[[object, bool], Awaitable[None]] | None = None,
    ) -> None:
        self._actor = actor
        self._inner = inner

    async def check(self, aggregate: object, is_new: bool) -> None:
        """保存前に本人特定を確かめ、続けて内側の境界へ委ねる。"""
        if not isinstance(self._actor, ResolvedActorContext):
            raise UnavailableIdentityError(
                "更新には本人に結び付いた個人アカウントが必要です。"
            )
        if self._inner is not None:
            await self._inner(aggregate, is_new)


__all__ = ["ResolvedActorWriteGuard"]
