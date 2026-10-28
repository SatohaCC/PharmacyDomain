"""Repositoryから参照用DTOを投影するアダプタ。保存は行わない。"""

from app.application.common.exceptions import NotFoundError
from app.application.identity.commands.services.repositories import IdentityRepositories
from app.application.identity.interfaces.get_user_query_reader import GetUserQueryReader
from app.application.identity.queries.dtos.identity_views import MembershipViewDto
from app.domain.corporate.identifiers import CorporateId
from app.domain.identity.identifiers import CorporateMembershipId


class GetUserProjection(GetUserQueryReader):
    """本人を広域検索せず、対象法人に属するアクセス権から参照する。

    本人IDから引く入口を作ると、法人をまたいで人を探せてしまう。入口は必ず
    「この法人のアクセス権」に限る。
    """

    def __init__(self, repositories: IdentityRepositories) -> None:
        self._repositories = repositories

    async def read(self, corporate_id: str, membership_id: str) -> MembershipViewDto:
        """他法人のアクセス権は存在を隠して未検出として扱う。"""
        corporate = CorporateId.parse(corporate_id)
        membership = await self._repositories.memberships.get(
            CorporateMembershipId.parse(membership_id)
        )
        if membership is None or membership.corporate_id != corporate:
            raise NotFoundError()
        account = await self._repositories.accounts.get(membership.account_id)
        if account is None:
            raise NotFoundError()
        return MembershipViewDto.from_entities(membership, account)
