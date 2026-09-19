"""未受諾の招待を取り消すユースケース。"""

from app.application.access_control import CorporateAccessBoundary, Permission
from app.application.common import UnitOfWork
from app.application.common.exceptions import NotFoundError
from app.application.common.organization_lock import OrganizationLock
from app.domain.corporate.primitives import CorporateId
from app.domain.identity.primitives import UserInvitationId
from app.domain.identity.repository import UserInvitationRepository


class CancelInvitationUseCase:
    """自法人の招待を取り消す。受諾済みの取消は集約が拒否する。"""

    def __init__(
        self,
        invitations: UserInvitationRepository,
        access: CorporateAccessBoundary,
        unit_of_work: UnitOfWork,
        lock: OrganizationLock,
    ) -> None:
        self._invitations = invitations
        self._access = access
        self._unit_of_work = unit_of_work
        self._lock = lock

    async def execute(self, corporate_id: str, invitation_id: str) -> None:
        """他法人の招待は存在を隠して未検出として扱う。"""
        self._unit_of_work.ensure_active()
        corporate = CorporateId.parse(corporate_id)
        await self._lock.acquire("identity")
        await self._access.require_active(
            corporate_id=corporate, permission=Permission.MANAGE_STAFF
        )
        invitation = await self._invitations.get(UserInvitationId.parse(invitation_id))
        if invitation is None or invitation.corporate_id != corporate:
            raise NotFoundError()
        await self._invitations.save(invitation.cancel())


__all__ = ["CancelInvitationUseCase"]
