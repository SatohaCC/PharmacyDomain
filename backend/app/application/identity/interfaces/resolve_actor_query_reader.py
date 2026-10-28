"""Applicationのresolve_actor_query_readerを定義する。"""

from __future__ import annotations

from typing import Protocol

from app.application.access_control.boundary_models import ResolvedActorContext
from app.application.identity.boundary_models import VerifiedSubject


class ResolveActorQueryReader(Protocol):
    async def read(self, subject: VerifiedSubject) -> ResolvedActorContext:
        """認可済みの検索条件から、不変な参照結果だけを返す。"""
        ...
