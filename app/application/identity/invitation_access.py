"""未登録の本人の招待受諾へ管理者権限を与えない。"""

from typing import Never

from app.application.access_control.boundary import CorporateAccessBoundary
from app.application.access_control.models import (
    ActorContext,
    Permission,
)
from app.application.common.exceptions import AuthorizationError
from app.domain.corporate.corporate import Corporate
from app.domain.corporate.primitives import CorporateId


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
