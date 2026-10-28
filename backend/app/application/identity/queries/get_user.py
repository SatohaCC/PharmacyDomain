"""Applicationのget_userを定義する。"""

from __future__ import annotations

from app.application.access_control.boundary_models import (
    ActorRole,
    Permission,
    ResolvedActorContext,
)
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.common.exceptions import NotFoundError
from app.application.identity.interfaces.get_user_query_reader import GetUserQueryReader
from app.application.identity.queries.dtos.identity_views import MembershipViewDto
from app.domain.corporate.identifiers import CorporateId


class GetUserUseCase:
    def __init__(
        self, reader: GetUserQueryReader, access: CorporateAccessBoundary
    ) -> None:
        self._reader = reader
        self._access = access

    async def execute(self, corporate_id: str, membership_id: str) -> MembershipViewDto:
        """他法人のアクセス権は存在を隠して未検出として扱う。"""
        corporate = CorporateId.parse(corporate_id)
        actor = self._access.actor
        manager = isinstance(actor, ResolvedActorContext) and not actor.roles & {
            ActorRole.CORPORATE_ADMIN,
            ActorRole.VENDOR_SYSTEM_ADMIN,
        }
        await self._access.require_active(
            corporate_id=corporate,
            permission=Permission.MANAGE_STORE_USERS
            if manager
            else Permission.MANAGE_STAFF,
        )
        result = await self._reader.read(corporate_id, membership_id)
        if manager:
            assert isinstance(actor, ResolvedActorContext)
            if not {str(item.value) for item in actor.managed_store_ids} & set(
                result.store_ids
            ):
                raise NotFoundError()
        return result
