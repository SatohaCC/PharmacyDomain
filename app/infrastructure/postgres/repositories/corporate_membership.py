"""法人アクセス権の保存と有効所属の原子的な一意性。"""

from sqlalchemy import select

from app.domain.corporate.primitives import CorporateId
from app.domain.identity.exceptions import IdentityConflictError
from app.domain.identity.membership import CorporateMembership
from app.domain.identity.primitives import CorporateMembershipId, UserAccountId
from app.domain.identity.repository import CorporateMembershipRepository
from app.domain.staff.primitives import StaffId
from app.infrastructure.postgres.repository_base import (
    AggregateMapping,
    PostgresRepositoryBase,
)
from app.infrastructure.postgres.schema import corporate_memberships

MEMBERSHIP_MAPPING = AggregateMapping(
    table=corporate_memberships,
    aggregate_type=CorporateMembership,
    label="法人アクセス権",
    search_columns=lambda item: {
        "id": item.id.value,
        "corporate_id": item.corporate_id.value,
        "account_id": item.account_id.value,
        "staff_id": item.staff_id.value if item.staff_id is not None else None,
        "role": item.role.value,
        "status": item.status.value,
    },
)


class PostgresCorporateMembershipRepository(
    PostgresRepositoryBase, CorporateMembershipRepository
):
    """本人の法人アクセスは同時に一つまで許可する。"""

    async def get(
        self, membership_id: CorporateMembershipId
    ) -> CorporateMembership | None:
        return await self.get_by_id(MEMBERSHIP_MAPPING, membership_id)

    async def find_active_for_account(
        self, account_id: UserAccountId
    ) -> CorporateMembership | None:
        return await self.find_one(
            MEMBERSHIP_MAPPING,
            select(corporate_memberships).where(
                corporate_memberships.c.account_id == account_id.value,
                corporate_memberships.c.status == "active",
            ),
        )

    async def save(self, membership: CorporateMembership) -> None:
        await self.save_with_conflict_map(
            MEMBERSHIP_MAPPING,
            membership,
            conflicts={
                "uq_membership_active_account": IdentityConflictError,
                "uq_membership_account_corporate": IdentityConflictError,
                "ck_membership_person": IdentityConflictError,
                "ck_membership_identity_immutable": IdentityConflictError,
            },
        )

    async def list_by_corporate(
        self, corporate_id: CorporateId
    ) -> list[CorporateMembership]:
        return await self.find_all(
            MEMBERSHIP_MAPPING,
            select(corporate_memberships)
            .where(corporate_memberships.c.corporate_id == corporate_id.value)
            .order_by(corporate_memberships.c.id),
        )

    async def find_by_staff(self, staff_id: StaffId) -> CorporateMembership | None:
        return await self.find_one(
            MEMBERSHIP_MAPPING,
            select(corporate_memberships).where(
                corporate_memberships.c.staff_id == staff_id.value
            ),
        )
