"""Applicationのresolve_actorを定義する。"""

from __future__ import annotations

from app.application.access_control.boundary_models import ResolvedActorContext
from app.application.identity.boundary_models import VerifiedSubject
from app.application.identity.interfaces.resolve_actor_query_reader import (
    ResolveActorQueryReader,
)


class ResolveActorUseCase:
    def __init__(self, reader: ResolveActorQueryReader) -> None:
        self._reader = reader

    async def execute(self, subject: VerifiedSubject) -> ResolvedActorContext:
        """外部主体からアカウントと本人を引き、現在有効なアクセス権を照合する。

        出発点を外部主体にしているので、「主体を固定していないアカウント」は
        検索の時点で到達できない。分岐で除外していた頃は、その分岐を書き忘れると
        未固定のアカウントにだけ照合が効かなくなっていた。
        """
        return await self._reader.read(subject)
