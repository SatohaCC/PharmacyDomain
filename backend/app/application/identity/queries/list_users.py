"""Applicationのlist_usersを定義する。"""

from __future__ import annotations

from app.application.access_control.boundary_models import (
    ActorRole,
    Permission,
    ResolvedActorContext,
)
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.common.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, Page
from app.application.identity.interfaces.list_users_query_reader import (
    ListUsersQueryReader,
)
from app.application.identity.queries.dtos.identity_views import MembershipViewDto
from app.domain.corporate.identifiers import CorporateId
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.identity.identifiers import CorporateMembershipId


class ListUsersUseCase:
    def __init__(
        self, reader: ListUsersQueryReader, access: CorporateAccessBoundary
    ) -> None:
        self._reader = reader
        self._access = access

    async def execute(
        self,
        corporate_id: str,
        *,
        after: str | None = None,
        limit: int = DEFAULT_PAGE_SIZE,
    ) -> Page[MembershipViewDto]:
        """IDの昇順で並べ、続きがあればカーソルを返す。"""
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
        if not 1 <= limit <= MAX_PAGE_SIZE:
            raise DomainValidationError(
                f"件数は1から{MAX_PAGE_SIZE}で指定してください。"
            )
        CorporateMembershipId.parse(after) if after else None
        if manager:
            assert isinstance(actor, ResolvedActorContext)
            return await self._reader.read(
                corporate_id,
                after=after,
                limit=limit,
                store_ids=tuple(str(item.value) for item in actor.managed_store_ids),
            )
        return await self._reader.read(corporate_id, after=after, limit=limit)
