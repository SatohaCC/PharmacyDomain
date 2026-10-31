"""スタッフ本人対応の固定保存。"""

from sqlalchemy import select

from app.domain.corporate.identifiers import CorporateId
from app.domain.identity.entities import StaffPersonLink
from app.domain.identity.exceptions import IdentityConflictError
from app.domain.identity.repositories import StaffPersonLinkRepository
from app.domain.staff.identifiers import StaffId
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

    async def find_for_corporate(
        self, corporate_id: CorporateId, staff_id: StaffId
    ) -> StaffPersonLink | None:
        """法人スコープ内でスタッフと本人の対応を取得する。"""
        return await self.find_one(
            STAFF_PERSON_LINK_MAPPING,
            select(staff_person_links).where(
                staff_person_links.c.id == staff_id.value,
                staff_person_links.c.corporate_id == corporate_id.value,
            ),
        )

    async def save(self, link: StaffPersonLink) -> None:
        await self.save_with_conflict_map(
            STAFF_PERSON_LINK_MAPPING,
            link,
            conflicts={
                "ck_staff_person_immutable": IdentityConflictError,
                "ck_staff_person_corporate": IdentityConflictError,
            },
        )
