"""法人の利用者権限を1件参照するユースケース。"""

from app.application.access_control.boundary import CorporateAccessBoundary
from app.application.access_control.models import Permission
from app.application.common.exceptions import NotFoundError
from app.application.identity.dto import MembershipViewDto
from app.application.identity.support import IdentityRepositories
from app.domain.corporate.primitives import CorporateId
from app.domain.identity.primitives import CorporateMembershipId


class GetUserUseCase:
    """本人を広域検索せず、対象法人に属するアクセス権から参照する。

    本人IDから引く入口を作ると、法人をまたいで人を探せてしまう。入口は必ず
    「この法人のアクセス権」に限る。
    """

    def __init__(
        self,
        repositories: IdentityRepositories,
        access: CorporateAccessBoundary,
    ) -> None:
        self._repositories = repositories
        self._access = access

    async def execute(self, corporate_id: str, membership_id: str) -> MembershipViewDto:
        """他法人のアクセス権は存在を隠して未検出として扱う。"""
        corporate = CorporateId.parse(corporate_id)
        await self._access.require_active(
            corporate_id=corporate, permission=Permission.MANAGE_STAFF
        )
        membership = await self._repositories.memberships.get(
            CorporateMembershipId.parse(membership_id)
        )
        if membership is None or membership.corporate_id != corporate:
            raise NotFoundError()
        account = await self._repositories.accounts.get(membership.account_id)
        if account is None:
            raise NotFoundError()
        return MembershipViewDto.from_entities(membership, account)


__all__ = ["GetUserUseCase"]
