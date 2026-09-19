"""保存の手前に掛ける境界と、その並べ方。"""

from collections.abc import Awaitable, Callable, Sequence

from app.application.access_control.models import ActorContext, ResolvedActorContext
from app.application.identity.resolve_actor import UnavailableIdentityError

#: 保存前に呼ばれる境界。集約と「このトランザクションで初めて書くか」を受ける。
WriteGuard = Callable[[object, bool], Awaitable[None]]


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

    def __init__(self, actor: ActorContext) -> None:
        self._actor = actor

    async def check(self, aggregate: object, is_new: bool) -> None:
        """保存前に本人特定を確かめる。"""
        if not isinstance(self._actor, ResolvedActorContext):
            raise UnavailableIdentityError(
                "更新には本人に結び付いた個人アカウントが必要です。"
            )


class CompositeWriteGuard:
    """複数の境界を宣言された順に適用する。

    境界を入れ子の引数で繋ぐと、Composition Root の1行に「どれが外側か」という
    意味が生まれ、増えるたびに読みにくくなる。並びとして書けば、掛かる順序が
    そのまま一覧になる。
    """

    def __init__(self, guards: Sequence[WriteGuard]) -> None:
        self._guards = tuple(guards)

    @property
    def guards(self) -> tuple[WriteGuard, ...]:
        """適用する境界を宣言された順で返す。"""
        return self._guards

    async def check(self, aggregate: object, is_new: bool) -> None:
        """全ての境界を順に適用する。"""
        for guard in self._guards:
            await guard(aggregate, is_new)


__all__ = ["CompositeWriteGuard", "ResolvedActorWriteGuard", "WriteGuard"]
