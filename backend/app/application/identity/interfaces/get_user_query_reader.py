"""Applicationのget_user_query_readerを定義する。"""

from __future__ import annotations

from typing import Protocol

from app.application.identity.queries.dtos.identity_views import MembershipViewDto


class GetUserQueryReader(Protocol):
    async def read(self, corporate_id: str, membership_id: str) -> MembershipViewDto:
        """認可済みの検索条件から、不変な参照結果だけを返す。"""
        ...
