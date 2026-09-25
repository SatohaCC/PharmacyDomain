"""招待の状態を参照するユースケース。"""

from app.application.access_control.boundary import CorporateAccessBoundary
from app.application.access_control.models import Permission
from app.application.common.exceptions import NotFoundError
from app.application.identity.dto import InvitationViewDto
from app.domain.corporate.primitives import CorporateId
from app.domain.identity.primitives import UserInvitationId
from app.domain.identity.repository import UserInvitationRepository


class GetInvitationUseCase:
    """招待の状態だけを返す。ダイジェストも秘密も返さない。"""

    def __init__(
        self,
        invitations: UserInvitationRepository,
        access: CorporateAccessBoundary,
    ) -> None:
        self._invitations = invitations
        self._access = access

    async def execute(self, corporate_id: str, invitation_id: str) -> InvitationViewDto:
        """他法人の招待は存在を隠して未検出として扱う。"""
        corporate = CorporateId.parse(corporate_id)
        await self._access.require_active(
            corporate_id=corporate, permission=Permission.MANAGE_STAFF
        )
        invitation = await self._invitations.get(UserInvitationId.parse(invitation_id))
        if invitation is None or invitation.corporate_id != corporate:
            raise NotFoundError()
        return InvitationViewDto.from_entity(invitation)


__all__ = ["GetInvitationUseCase"]
