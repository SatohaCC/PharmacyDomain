"""Repositoryから参照用DTOを投影するアダプタ。保存は行わない。"""

from app.application.common.exceptions import NotFoundError
from app.application.identity.interfaces.get_invitation_query_reader import (
    GetInvitationQueryReader,
)
from app.application.identity.queries.dtos.identity_views import InvitationViewDto
from app.domain.corporate.identifiers import CorporateId
from app.domain.identity.identifiers import UserInvitationId
from app.domain.identity.repositories import UserInvitationRepository


class GetInvitationProjection(GetInvitationQueryReader):
    """招待の状態だけを返す。ダイジェストも秘密も返さない。"""

    def __init__(self, invitations: UserInvitationRepository) -> None:
        self._invitations = invitations

    async def read(self, corporate_id: str, invitation_id: str) -> InvitationViewDto:
        """他法人の招待は存在を隠して未検出として扱う。"""
        corporate = CorporateId.parse(corporate_id)
        invitation = await self._invitations.get(UserInvitationId.parse(invitation_id))
        if invitation is None or invitation.corporate_id != corporate:
            raise NotFoundError()
        return InvitationViewDto.from_entity(invitation)
