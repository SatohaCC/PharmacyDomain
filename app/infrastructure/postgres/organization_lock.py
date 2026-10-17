"""法人単位の直列化に用いるPostgreSQLのトランザクションロック。"""

from sqlalchemy import func, select

from app.application.common.organization_lock import OrganizationLock
from app.infrastructure.postgres.connection import PostgresUnitOfWork


class PostgresOrganizationLock(OrganizationLock):
    """同一キーをトランザクション終了まで排他的に保持する。"""

    def __init__(self, unit_of_work: PostgresUnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    async def acquire(self, key: str) -> None:
        await self._unit_of_work.session.execute(
            select(func.pg_advisory_xact_lock(func.hashtextextended(key, 0))),
        )
