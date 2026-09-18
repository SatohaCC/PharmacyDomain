"""スタッフ本人対応の固定保存。"""

from app.domain.identity.exceptions import IdentityConflictError
from app.domain.identity.repository import StaffPersonLinkRepository
from app.domain.identity.staff_person_link import StaffPersonLink
from app.domain.staff.primitives import StaffId
from app.infrastructure.postgres.repository_base import (
    AggregateMapping,
    PostgresRepositoryBase,
)
from app.infrastructure.postgres.schema import staff_person_links

STAFF_PERSON_LINK_MAPPING = AggregateMapping(
    table=staff_person_links,
    aggregate_type=StaffPersonLink,
    label="スタッフ本人対応",
    search_columns=lambda item: {
        "id": item.id.value,
        "corporate_id": item.corporate_id.value,
        "person_id": item.person_id.value,
    },
)


class PostgresStaffPersonLinkRepository(
    PostgresRepositoryBase, StaffPersonLinkRepository
):
    """別人への付け替えと法人の不一致をDBでも拒否する。"""

    async def get(self, staff_id: StaffId) -> StaffPersonLink | None:
        return await self.get_by_id(STAFF_PERSON_LINK_MAPPING, staff_id)

    async def save(self, link: StaffPersonLink) -> None:
        await self.save_with_conflict_map(
            STAFF_PERSON_LINK_MAPPING,
            link,
            conflicts={
                "ck_staff_person_immutable": IdentityConflictError,
                "ck_staff_person_corporate": IdentityConflictError,
            },
        )
