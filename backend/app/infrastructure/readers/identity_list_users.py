"""Repositoryから参照用DTOを投影するアダプタ。保存は行わない。"""

from app.application.common.exceptions import NotFoundError
from app.application.common.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, Page
from app.application.identity.commands.services.repositories import IdentityRepositories
from app.application.identity.interfaces.list_users_query_reader import (
    ListUsersQueryReader,
)
from app.application.identity.queries.dtos.identity_views import MembershipViewDto
from app.domain.corporate.identifiers import CorporateId
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.identity.entities import CorporateMembership
from app.domain.identity.identifiers import CorporateMembershipId
from app.domain.staff.identifiers import StaffId
from app.domain.staff.repositories import StaffCatalogRepository


class ListUsersProjection(ListUsersQueryReader):
    """自法人のアクセス権をID順で返す。秘密・外部主体は返さない。"""

    def __init__(
        self,
        repositories: IdentityRepositories,
        staffs: StaffCatalogRepository | None = None,
    ) -> None:
        self._repositories = repositories
        self._staffs = staffs

    async def read(
        self,
        corporate_id: str,
        *,
        after: str | None = None,
        limit: int = DEFAULT_PAGE_SIZE,
        store_ids: tuple[str, ...] | None = None,
    ) -> Page[MembershipViewDto]:
        """IDの昇順で並べ、続きがあればカーソルを返す。"""
        corporate = CorporateId.parse(corporate_id)
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
            item
            for item in rows
            if (after_id is None or item.id.value > after_id.value)
            and (
                store_ids is None
                or any(str(store.value) in store_ids for store in item.store_ids)
            )
        ]
        page = rows[:limit]
        staff_names: dict[StaffId, str] = {}
        if self._staffs is not None and any(item.staff_id is not None for item in page):
            staff_names = {
                staff.id: staff.names.kanji.full_name
                for staff in await self._staffs.list_by_corporate_id(corporate)
            }
        return Page(
            items=tuple([await self._view(item, staff_names) for item in page]),
            next_cursor=str(page[-1].id.value) if len(rows) > limit else None,
        )

    async def _view(
        self,
        membership: CorporateMembership,
        staff_names: dict[StaffId, str],
    ) -> MembershipViewDto:
        """権限と、その土台のアカウント状態を1つの公開値へまとめる。"""
        account = await self._repositories.accounts.get(membership.account_id)
        if account is None:
            raise NotFoundError()
        staff_name = (
            staff_names.get(membership.staff_id)
            if membership.staff_id is not None
            else None
        )
        return MembershipViewDto.from_entities(
            membership, account, staff_name=staff_name
        )
