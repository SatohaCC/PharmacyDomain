"""Applicationのcorporate_accessを定義する。"""

from __future__ import annotations

from typing import Protocol

from app.application.access_control.boundary_models import ActorContext, Permission
from app.domain.corporate.entities import Corporate
from app.domain.corporate.identifiers import CorporateId


class CorporateAccessBoundary(Protocol):
    """対象法人の認可・存在・有効状態を確認して法人集約を返す境界。"""

    @property
    def actor(self) -> ActorContext:
        """認可に使用する信頼済み操作主体を返す。"""
        ...

    async def require_active(
        self, *, corporate_id: CorporateId, permission: Permission
    ) -> Corporate:
        """権限を確認し、有効な対象法人を返す。"""
        ...
