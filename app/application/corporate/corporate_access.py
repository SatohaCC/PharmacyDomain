"""対象法人の存在・有効状態・操作権限をまとめて確認するサービス。"""

from __future__ import annotations

from app.application.access_control.models import ActorContext, Permission
from app.application.access_control.policy import AuthorizationService
from app.application.corporate.support import (
    load_active_corporate_or_raise,
    load_corporate_or_raise,
)
from app.domain.corporate.corporate import Corporate
from app.domain.corporate.primitives import CorporateId
from app.domain.corporate.repository import CorporateRepository


class CorporateAccessService:
    """認可済み操作主体が対象法人を利用できることを確認する。"""

    def __init__(
        self,
        repository: CorporateRepository,
        authorization: AuthorizationService,
    ) -> None:
        self._repository = repository
        self._authorization = authorization

    @property
    def actor(self) -> ActorContext:
        """認可と監査で共有する信頼済み操作主体を返す。"""
        return self._authorization.actor

    async def require_active(
        self,
        *,
        corporate_id: CorporateId,
        permission: Permission,
    ) -> Corporate:
        """権限を確認し、有効な対象法人を返す。"""
        self._authorization.require(
            permission=permission,
            target_corporate_id=corporate_id,
        )
        return await load_active_corporate_or_raise(self._repository, corporate_id)

    async def require_existing(
        self,
        *,
        corporate_id: CorporateId,
        permission: Permission,
    ) -> Corporate:
        """権限を確認し、状態にかかわらず対象法人を返す。"""
        self._authorization.require(
            permission=permission,
            target_corporate_id=corporate_id,
        )
        return await load_corporate_or_raise(self._repository, corporate_id)

    def require_vendor_system_admin(self, *, permission: Permission) -> None:
        """法人をまだ特定しないベンダー管理者専用操作を確認する。"""
        self._authorization.require_vendor_system_admin(permission=permission)
