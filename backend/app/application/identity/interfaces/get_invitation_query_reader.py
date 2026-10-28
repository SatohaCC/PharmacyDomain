"""Applicationのget_invitation_query_readerを定義する。"""

from __future__ import annotations

from typing import Protocol

from app.application.identity.queries.dtos.identity_views import InvitationViewDto


class GetInvitationQueryReader(Protocol):
    async def read(self, corporate_id: str, invitation_id: str) -> InvitationViewDto:
        """認可済みの検索条件から、不変な参照結果だけを返す。"""
        ...
