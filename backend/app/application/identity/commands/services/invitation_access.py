"""Applicationのinvitation_accessを定義する。"""

from __future__ import annotations

from typing import Never

from app.application.access_control.boundary_models import ActorContext, Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.common.exceptions import AuthorizationError
from app.domain.corporate.entities import Corporate
from app.domain.corporate.identifiers import CorporateId


class InvitationOnlyAccess(CorporateAccessBoundary):
    """招待受諾は検証済み本人と招待だけで認可し、通常管理操作を拒否する。"""

    @property
    def actor(self) -> ActorContext:
        return self._deny()

    async def require_active(
        self, *, corporate_id: CorporateId, permission: Permission
    ) -> Corporate:
        return self._deny()

    def _deny(self) -> Never:
        """未登録本人へ通常の管理権限を付与しない。"""
        raise AuthorizationError("招待受諾の経路で通常の管理操作はできません。")
