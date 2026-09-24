"""旧店舗payloadを移行しても架空の本人・過去監査を作らない。"""

from datetime import UTC, datetime

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Connection, func, insert, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.domain.store.lifecycle import StoreStatus
from app.infrastructure.postgres import schema
from app.infrastructure.postgres.codec import encode_aggregate
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.infrastructure.postgres.repositories.corporate import CORPORATE_MAPPING
from app.infrastructure.postgres.repositories.repository_set import (
    PostgresRepositorySet,
)
from app.infrastructure.postgres.repositories.store import STORE_MAPPING
from tests.factories.store_factory import create_store
from tests.infrastructure.postgres.helpers import create_corporate, ordered_migrations


@pytest.mark.asyncio
async def test_旧店舗を稼働中かつ履歴空へ移行し本人と過去監査を捏造しない(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    corporate = create_corporate()
    store = create_store(
        corporate_id=corporate.id,
        code="KEEP001",
        insurance_pharmacy_number="1341234567",
    )

    def migrate(connection: Connection) -> None:
        schema.metadata.drop_all(connection)
        modules = ordered_migrations()
        with Operations.context(MigrationContext.configure(connection=connection)):
            for module in modules[:-1]:
                module.upgrade()
            now = datetime(2026, 9, 1, tzinfo=UTC)
            connection.execute(
                insert(schema.corporates).values(
                    **CORPORATE_MAPPING.row_values(corporate),
                    version=1,
                    created_at=now,
                    updated_at=now,
                )
            )
            values = STORE_MAPPING.row_values(store)
            payload = encode_aggregate(store)
            payload.pop("status")
            payload.pop("status_history")
            values["payload"] = payload
            connection.execute(
                insert(schema.stores).values(
                    **values, version=1, created_at=now, updated_at=now
                )
            )
            modules[-1].upgrade()

    async with engine.begin() as connection:
        await connection.run_sync(migrate)
    async with PostgresUnitOfWork(session_factory) as work:
        actual = await PostgresRepositorySet.create(work).store.get(store.id)
        assert actual is not None
        assert actual.status == StoreStatus.ACTIVE and actual.status_history == ()
        assert actual.code == store.code
        assert actual.insurance_pharmacy_number == store.insurance_pharmacy_number
        assert (
            await work.session.scalar(
                select(func.count()).select_from(schema.account_people)
            )
            == 0
        )
        assert (
            await work.session.scalar(
                select(func.count()).select_from(schema.operation_audits)
            )
            == 0
        )
