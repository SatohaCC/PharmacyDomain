"""管理薬剤師任命の原子的な期間競合防御。"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import Range

from app.domain.corporate.primitives import CorporateId
from app.domain.staff.primitives import StaffId
from app.domain.store.manager_assignment import (
    ManagerAssignmentStatus,
    ManagerPersonUnresolvedError,
    StoreManagerAssignment,
    StoreManagerAssignmentId,
)
from app.domain.store.manager_repository import (
    ManagerAssignmentConflictError,
    ManagerExclusiveDutyConflictError,
    StoreManagerAssignmentRepository,
)
from app.domain.store.primitives import StoreId
from app.infrastructure.postgres.repository_base import (
    AggregateMapping,
    PostgresRepositoryBase,
)
from app.infrastructure.postgres.schema import store_manager_assignments

MANAGER_ASSIGNMENT_MAPPING = AggregateMapping(
    table=store_manager_assignments,
    aggregate_type=StoreManagerAssignment,
    label="管理薬剤師任命",
    search_columns=lambda item: {
        "id": item.id.value,
        "corporate_id": item.corporate_id.value,
        "store_id": item.store_id.value,
        "staff_id": item.staff_id.value,
        "person_id": item.person_id.value,
        "status": item.status.value,
        "period": Range(item.period.starts_on, item.period.ends_on, bounds="[]"),
    },
)


class PostgresStoreManagerAssignmentRepository(
    PostgresRepositoryBase, StoreManagerAssignmentRepository
):
    """任命期間は店舗とスタッフそれぞれの排他制約で保護する。"""

    async def get(
        self, assignment_id: StoreManagerAssignmentId
    ) -> StoreManagerAssignment | None:
        return await self.get_by_id(MANAGER_ASSIGNMENT_MAPPING, assignment_id)

    async def list_by_store(
        self, corporate_id: CorporateId, store_id: StoreId
    ) -> list[StoreManagerAssignment]:
        return await self.find_all(
            MANAGER_ASSIGNMENT_MAPPING,
            select(store_manager_assignments)
            .where(
                store_manager_assignments.c.corporate_id == corporate_id.value,
                store_manager_assignments.c.store_id == store_id.value,
            )
            .order_by(store_manager_assignments.c.id),
        )

    async def list_by_staff(
        self, corporate_id: CorporateId, staff_id: StaffId
    ) -> list[StoreManagerAssignment]:
        return await self.find_all(
            MANAGER_ASSIGNMENT_MAPPING,
            select(store_manager_assignments)
            .where(
                store_manager_assignments.c.corporate_id == corporate_id.value,
                store_manager_assignments.c.staff_id == staff_id.value,
            )
            .order_by(store_manager_assignments.c.id),
        )

    async def find_effective(
        self, corporate_id: CorporateId, store_id: StoreId, as_of: date
    ) -> StoreManagerAssignment | None:
        """任命期間を含む確定行を引く。

        期間は終了日を含む閉区間として ``daterange`` へ写してあるので、含有
        判定をそのまま範囲演算子へ任せられる。同じ店舗で重なる確定行は排他
        制約が拒否するため、結果は高々1件に定まる。
        """
        return await self.find_one(
            MANAGER_ASSIGNMENT_MAPPING,
            select(store_manager_assignments).where(
                store_manager_assignments.c.corporate_id == corporate_id.value,
                store_manager_assignments.c.store_id == store_id.value,
                store_manager_assignments.c.status
                == ManagerAssignmentStatus.CONFIRMED.value,
                store_manager_assignments.c.period.contains(as_of),
            ),
        )

    async def save(self, assignment: StoreManagerAssignment) -> None:
        await self.save_with_conflict_map(
            MANAGER_ASSIGNMENT_MAPPING,
            assignment,
            conflicts={
                "ex_manager_store_period": ManagerAssignmentConflictError,
                "ex_manager_person_period": ManagerExclusiveDutyConflictError,
                # 本人の対応が無いスタッフは、複合外部キーで弾かれる。
                "fk_store_manager_assignments_staff_person": (
                    ManagerPersonUnresolvedError
                ),
            },
        )
