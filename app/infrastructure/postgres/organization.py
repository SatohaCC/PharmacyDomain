"""法人単位の直列化と閉局前の未完了業務照会。"""

from sqlalchemy import exists, or_, select, text

from app.application.common.organization_lock import OrganizationLock
from app.application.store.management import StoreWorkBoundary
from app.domain.corporate.primitives import CorporateId
from app.domain.store.primitives import StoreId
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.infrastructure.postgres.schema import dispensing_processes, prescriptions


class PostgresOrganizationLock(OrganizationLock):
    """同一キーをトランザクション終了まで排他的に保持する。"""

    def __init__(self, unit_of_work: PostgresUnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    async def acquire(self, key: str) -> None:
        await self._unit_of_work.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": key},
        )


class PostgresStoreWorkBoundary(StoreWorkBoundary):
    """処方箋と調剤の終端以外をDBで照会する。"""

    def __init__(self, unit_of_work: PostgresUnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    async def has_unfinished(
        self, corporate_id: CorporateId, store_id: StoreId
    ) -> bool:
        prescription = exists(
            select(prescriptions.c.id).where(
                prescriptions.c.corporate_id == corporate_id.value,
                prescriptions.c.store_id == store_id.value,
                prescriptions.c.status.not_in(["dispensed", "cancelled"]),
            )
        )
        dispensing = exists(
            select(dispensing_processes.c.id).where(
                dispensing_processes.c.corporate_id == corporate_id.value,
                dispensing_processes.c.store_id == store_id.value,
                dispensing_processes.c.status.not_in(["completed", "cancelled"]),
            )
        )
        return bool(
            await self._unit_of_work.session.scalar(
                select(or_(prescription, dispensing))
            )
        )
