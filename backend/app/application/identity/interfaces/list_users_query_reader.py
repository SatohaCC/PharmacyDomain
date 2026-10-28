"""Applicationのlist_users_query_readerを定義する。"""

from __future__ import annotations

from typing import Protocol

from app.application.common.pagination import DEFAULT_PAGE_SIZE, Page
from app.application.identity.queries.dtos.identity_views import MembershipViewDto


class ListUsersQueryReader(Protocol):
    async def read(
        self,
        corporate_id: str,
        *,
        after: str | None = None,
        limit: int = DEFAULT_PAGE_SIZE,
    ) -> Page[MembershipViewDto]:
        """認可済みの検索条件から、不変な参照結果だけを返す。"""
        ...
