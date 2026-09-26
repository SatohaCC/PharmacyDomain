"""薬歴の取込来歴を実PostgreSQLとmigrationで検証する。"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Connection, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.infrastructure.postgres.repositories.repository_set import (
    PostgresRepositorySet,
)
from tests.factories.medication_history_factory import (
    create_nsips_draft_record,
    create_record,
)
from tests.infrastructure.postgres.helpers import ordered_migrations


@pytest.mark.asyncio
async def test_tc22_NULL指導日時の薬歴を保存して一覧順を決定できる(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    imported_at = datetime(2026, 8, 24, 4, 0, tzinfo=UTC)
    draft_earlier = create_nsips_draft_record(imported_at=imported_at)
    draft_later = create_nsips_draft_record(
        corporate_id=draft_earlier.corporate_id,
        store_id=draft_earlier.store_id,
        patient_id=draft_earlier.patient_id,
        imported_at=imported_at,
    )
    counseled_at = datetime(2026, 8, 24, 5, 0, tzinfo=UTC)
    counseled = create_record(
        corporate_id=draft_earlier.corporate_id,
        store_id=draft_earlier.store_id,
        patient_id=draft_earlier.patient_id,
        counseled_at=counseled_at,
    )

    async with PostgresUnitOfWork(session_factory) as work:
        repository = PostgresRepositorySet.create(work).medication_history
        await repository.save(draft_earlier)
        await repository.save(draft_later)
        await repository.save(counseled)
        await work.commit()

    async with PostgresUnitOfWork(session_factory) as work:
        repository = PostgresRepositorySet.create(work).medication_history
        first = await repository.list_by_patient(
            corporate_id=draft_earlier.corporate_id,
            patient_id=draft_earlier.patient_id,
        )
        second = await repository.list_by_patient(
            corporate_id=draft_earlier.corporate_id,
            patient_id=draft_earlier.patient_id,
        )

    assert first[0].id == counseled.id
    assert first[0].counseled_at is not None
    assert first[0].counseled_at.value == counseled_at
    assert first[1].counseled_at is None and first[2].counseled_at is None
    assert [record.id for record in first] == [record.id for record in second]
    assert [record.id.value for record in first[1:]] == sorted(
        (draft_earlier.id.value, draft_later.id.value), reverse=True
    )


@pytest.mark.asyncio
async def test_tc23_NULL可能化migrationは_既存の指導日時を保持する(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    record = create_record(counseled_at=datetime(2026, 8, 24, 5, 0, tzinfo=UTC))
    expected_counseled_at = record.counseled_at
    assert expected_counseled_at is not None
    async with PostgresUnitOfWork(session_factory) as work:
        await PostgresRepositorySet.create(work).medication_history.save(record)
        await work.commit()

    async with engine.begin() as connection:
        await connection.execute(
            text(
                "ALTER TABLE medication_history_records "
                "ALTER COLUMN counseled_at SET NOT NULL"
            )
        )
        migration = next(
            item
            for item in ordered_migrations()
            if str(item.revision) == "20260925_0007"
        )

        def upgrade(connection: Connection) -> None:
            with Operations.context(MigrationContext.configure(connection=connection)):
                migration.upgrade()

        await connection.run_sync(upgrade)

    async with PostgresUnitOfWork(session_factory) as work:
        restored = await PostgresRepositorySet.create(work).medication_history.get(
            corporate_id=record.corporate_id,
            record_id=record.id,
        )

    assert restored is not None
    assert restored.counseled_at is not None
    assert restored.counseled_at.value == expected_counseled_at.value


@pytest.mark.asyncio
async def test_tc24_NULL指導日時の下書きがあると_downgradeはデータを変えず失敗する(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    record = create_nsips_draft_record()
    async with PostgresUnitOfWork(session_factory) as work:
        await PostgresRepositorySet.create(work).medication_history.save(record)
        await work.commit()

    migration = next(
        item for item in ordered_migrations() if str(item.revision) == "20260925_0007"
    )

    def downgrade(connection: Connection) -> None:
        with Operations.context(MigrationContext.configure(connection=connection)):
            migration.downgrade()

    with pytest.raises(RuntimeError, match="未確定"):
        async with engine.begin() as connection:
            await connection.run_sync(downgrade)

    async with PostgresUnitOfWork(session_factory) as work:
        restored = await PostgresRepositorySet.create(work).medication_history.get(
            corporate_id=record.corporate_id,
            record_id=record.id,
        )

    assert restored is not None
    assert restored.counseled_at is None
    assert restored.imported_at == record.imported_at
