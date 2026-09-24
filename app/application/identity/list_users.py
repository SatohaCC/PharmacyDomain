"""法人の利用者権限を一覧するユースケース。"""

from app.application.access_control.boundary import CorporateAccessBoundary
from app.application.access_control.models import Permission
from app.application.common.exceptions import NotFoundError
from app.application.common.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, Page
from app.application.identity.dto import MembershipViewDto
from app.application.identity.support import IdentityRepositories
from app.domain.corporate.primitives import CorporateId
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.identity.membership import CorporateMembership
from app.domain.identity.primitives import CorporateMembershipId


class ListUsersUseCase:
    """自法人のアクセス権をID順で返す。秘密・外部主体は返さない。"""

    def __init__(
        self,
        repositories: IdentityRepositories,
        access: CorporateAccessBoundary,
    ) -> None:
        self._repositories = repositories
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
        after_id = CorporateMembershipId.parse(after) if after else None
        rows = sorted(
            await self._repositories.memberships.list_by_corporate(corporate),
            key=lambda item: item.id.value,
        )
        rows = [
            item for item in rows if after_id is None or item.id.value > after_id.value
        ]
        page = rows[:limit]
        return Page(
            items=tuple([await self._view(item) for item in page]),
            next_cursor=str(page[-1].id.value) if len(rows) > limit else None,
        )

    async def _view(self, membership: CorporateMembership) -> MembershipViewDto:
        """権限と、その土台のアカウント状態を1つの公開値へまとめる。"""
        account = await self._repositories.accounts.get(membership.account_id)
        if account is None:
            raise NotFoundError()
        return MembershipViewDto.from_entities(membership, account)


__all__ = ["ListUsersUseCase"]
