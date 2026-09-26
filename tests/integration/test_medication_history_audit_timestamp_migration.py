"""薬歴登録日時の検索列・移行を実PostgreSQLで検証する。"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Connection, insert, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.domain.medication_history.medication_history_record import (
    MedicationHistoryRecord,
)
from app.domain.medication_history.primitives import FollowUpRecordedTimestamp
from app.infrastructure.postgres import schema
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.infrastructure.postgres.repositories.medication_history import (
    MEDICATION_HISTORY_RECORD_MAPPING,
)
from app.infrastructure.postgres.repositories.repository_set import (
    PostgresRepositorySet,
)
from tests.factories.medication_history_factory import create_record
from tests.infrastructure.postgres.helpers import ordered_migrations

_TARGET_REVISION = "20260926_0009"


def _run_revision(
    connection: Connection,
    *,
    operation: str,
    modules: list[Any],
) -> None:
    """指定したmigrationを同期接続で実行する。"""
    with Operations.context(MigrationContext.configure(connection=connection)):
        for module in modules:
            getattr(module, operation)()


def _prepare_preceding_schema(connection: Connection) -> tuple[list[Any], Any]:
    """対象migrationの直前までのスキーマを作る。"""
    schema.metadata.drop_all(connection, checkfirst=True)
    modules = ordered_migrations()
    target = next(
        module for module in modules if str(module.revision) == _TARGET_REVISION
    )
    preceding = modules[: modules.index(target)]
    _run_revision(connection, operation="upgrade", modules=preceding)
    return modules, target


def _legacy_row_values(record: MedicationHistoryRecord) -> dict[str, object]:
    """登録日時検索列・payloadのない旧薬歴行を組み立てる。"""
    values = MEDICATION_HISTORY_RECORD_MAPPING.row_values(record)
    values.pop("recorded_at", None)
    payload = values["payload"]
    assert isinstance(payload, dict)
    payload.pop("recorded_at", None)
    now = datetime(2026, 9, 20, tzinfo=UTC)
    values.update(version=3, created_at=now, updated_at=now)
    return values


@pytest.mark.asyncio
async def test_tc44_15_PostgreSQL一覧は登録日時とIDで同時刻を並べる(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    occurred_at = datetime(2026, 8, 24, 5, 0, tzinfo=UTC)
    first_registered = replace(
        create_record(counseled_at=occurred_at),
        recorded_at=FollowUpRecordedTimestamp(occurred_at + timedelta(minutes=1)),
    )
    second_registered = replace(
        create_record(
            corporate_id=first_registered.corporate_id,
            store_id=first_registered.store_id,
            patient_id=first_registered.patient_id,
            counseled_at=occurred_at,
        ),
        recorded_at=FollowUpRecordedTimestamp(occurred_at + timedelta(minutes=3)),
    )
    tied_registered = replace(
        create_record(
            corporate_id=first_registered.corporate_id,
            store_id=first_registered.store_id,
            patient_id=first_registered.patient_id,
            counseled_at=occurred_at,
        ),
        recorded_at=FollowUpRecordedTimestamp(occurred_at + timedelta(minutes=3)),
    )
    legacy = create_record(
        corporate_id=first_registered.corporate_id,
        store_id=first_registered.store_id,
        patient_id=first_registered.patient_id,
        counseled_at=occurred_at,
    )
    records = (first_registered, second_registered, tied_registered, legacy)

    async with PostgresUnitOfWork(session_factory) as work:
        repository = PostgresRepositorySet.create(work).medication_history
        for record in reversed(records):
            await repository.save(record)
        await work.commit()

    async with PostgresUnitOfWork(session_factory) as work:
        repository = PostgresRepositorySet.create(work).medication_history
        actual = await repository.list_by_patient(
            corporate_id=first_registered.corporate_id,
            patient_id=first_registered.patient_id,
        )

    assert [record.id for record in actual] == [
        *sorted(
            (second_registered.id, tied_registered.id),
            key=lambda item: item.value,
            reverse=True,
        ),
        first_registered.id,
        legacy.id,
    ]

    async with session_factory() as session:
        row = (
            (
                await session.execute(
                    select(schema.medication_history_records).where(
                        schema.medication_history_records.c.id
                        == second_registered.id.value
                    )
                )
            )
            .mappings()
            .one()
        )
    payload = row["payload"]
    assert isinstance(payload, dict)
    assert second_registered.recorded_at is not None
    expected_recorded_at = second_registered.recorded_at.value
    assert row["recorded_at"] == expected_recorded_at
    assert payload["recorded_at"] == expected_recorded_at.isoformat()


@pytest.mark.asyncio
async def test_tc44_17_migrationは既存行を保ち登録日時列を追加して戻せる(
    engine: AsyncEngine,
) -> None:
    old_record = create_record(counseled_at=datetime(2026, 8, 24, 5, 0, tzinfo=UTC))
    old_values = _legacy_row_values(old_record)
    old_payload_value = old_values["payload"]
    assert isinstance(old_payload_value, dict)
    old_payload = dict(old_payload_value)
    assert old_record.counseled_at is not None
    expected_old_counseled_at = old_record.counseled_at.value
    new_record = replace(
        create_record(
            corporate_id=old_record.corporate_id,
            store_id=old_record.store_id,
            patient_id=old_record.patient_id,
            counseled_at=datetime(2026, 8, 24, 6, 0, tzinfo=UTC),
        ),
        recorded_at=FollowUpRecordedTimestamp(datetime(2026, 8, 24, 6, 30, tzinfo=UTC)),
    )
    assert new_record.recorded_at is not None
    expected_new_recorded_at = new_record.recorded_at.value

    async with engine.connect() as connection:
        transaction = await connection.begin()
        try:

            def migrate(sync_connection: Connection) -> None:
                _, target = _prepare_preceding_schema(sync_connection)
                sync_connection.execute(
                    insert(schema.medication_history_records).values(**old_values)
                )
                _run_revision(sync_connection, operation="upgrade", modules=[target])

                old_row = (
                    sync_connection.execute(
                        text(
                            "SELECT recorded_at, payload, counseled_at "
                            "FROM medication_history_records WHERE id = :id"
                        ),
                        {"id": old_record.id.value},
                    )
                    .mappings()
                    .one()
                )
                assert old_row["recorded_at"] is None
                assert old_row["payload"] == old_payload
                assert old_row["counseled_at"] == expected_old_counseled_at

                new_values = MEDICATION_HISTORY_RECORD_MAPPING.row_values(new_record)
                now = datetime(2026, 9, 20, tzinfo=UTC)
                new_values.update(version=1, created_at=now, updated_at=now)
                sync_connection.execute(
                    insert(schema.medication_history_records).values(**new_values)
                )
                inserted = (
                    sync_connection.execute(
                        text(
                            "SELECT recorded_at, payload FROM medication_history_records "
                            "WHERE id = :id"
                        ),
                        {"id": new_record.id.value},
                    )
                    .mappings()
                    .one()
                )
                assert inserted["recorded_at"] == expected_new_recorded_at
                inserted_payload = inserted["payload"]
                assert isinstance(inserted_payload, dict)
                assert inserted_payload["recorded_at"] == (
                    expected_new_recorded_at.isoformat()
                )

                _run_revision(sync_connection, operation="downgrade", modules=[target])
                remaining_columns = {
                    str(row[0])
                    for row in sync_connection.execute(
                        text(
                            "SELECT column_name FROM information_schema.columns "
                            "WHERE table_name = 'medication_history_records'"
                        )
                    )
                }
                assert "recorded_at" not in remaining_columns
                remaining_payloads = {
                    str(row[0]): row[1]
                    for row in sync_connection.execute(
                        text(
                            "SELECT id, payload FROM medication_history_records "
                            "WHERE id IN (:old_id, :new_id)"
                        ),
                        {
                            "old_id": old_record.id.value,
                            "new_id": new_record.id.value,
                        },
                    )
                }
                assert remaining_payloads[str(old_record.id.value)] == old_payload
                assert remaining_payloads[str(new_record.id.value)]["recorded_at"] == (
                    expected_new_recorded_at.isoformat()
                )

            await connection.run_sync(migrate)
        finally:
            await transaction.rollback()
