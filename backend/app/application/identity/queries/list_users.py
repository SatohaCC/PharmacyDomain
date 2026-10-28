"""Applicationのlist_usersを定義する。"""

from __future__ import annotations

from app.application.access_control.boundary_models import Permission
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
        await self._access.require_active(
            corporate_id=corporate, permission=Permission.MANAGE_STAFF
        )
        if not 1 <= limit <= MAX_PAGE_SIZE:
            raise DomainValidationError(
                f"件数は1から{MAX_PAGE_SIZE}で指定してください。"
            )
        CorporateMembershipId.parse(after) if after else None
        return await self._reader.read(corporate_id, after=after, limit=limit)
