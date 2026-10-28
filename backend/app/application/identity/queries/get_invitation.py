"""Applicationのget_invitationを定義する。"""

from __future__ import annotations

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.identity.interfaces.get_invitation_query_reader import (
    GetInvitationQueryReader,
)
from app.application.identity.queries.dtos.identity_views import InvitationViewDto
from app.domain.corporate.identifiers import CorporateId


class GetInvitationUseCase:
    def __init__(
        self, reader: GetInvitationQueryReader, access: CorporateAccessBoundary
    ) -> None:
        self._reader = reader
        self._access = access

    async def execute(self, corporate_id: str, invitation_id: str) -> InvitationViewDto:
        """他法人の招待は存在を隠して未検出として扱う。"""
        corporate = CorporateId.parse(corporate_id)
        await self._access.require_active(
            corporate_id=corporate, permission=Permission.MANAGE_STAFF
        )
        return await self._reader.read(corporate_id, invitation_id)
