"""独立フォローアップ追加のmigrationをPostgreSQLで検証する。"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from io import StringIO
from typing import Any

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Connection, delete, insert, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.domain.medication_history.medication_history_record import (
    MedicationHistoryRecord,
)
from app.domain.medication_history.value_objects import ProfileUpdateIntents
from app.infrastructure.postgres import schema
from app.infrastructure.postgres.repositories.medication_history import (
    MEDICATION_HISTORY_RECORD_MAPPING,
)
from tests.factories.medication_history_factory import (
    create_allergy_intent,
    create_independent_follow_up_record,
    create_record,
    finalize_record_with_review,
)
from tests.infrastructure.postgres.helpers import ordered_migrations

_TARGET_REVISION = "20260926_0008"


def _old_row_values(record: MedicationHistoryRecord) -> dict[str, object]:
    """旧スキーマで保存されていた検索列とpayloadを作る。"""
    values = MEDICATION_HISTORY_RECORD_MAPPING.row_values(record)
    values.pop("record_kind")
    values.pop("source_record_id")
    payload = values["payload"]
    assert isinstance(payload, dict)
    payload.pop("record_kind")
    payload.pop("source_record_id")
    now = datetime(2026, 9, 20, tzinfo=UTC)
    values.update(version=4, created_at=now, updated_at=now)
    return values


def _run_revision(
    connection: Connection,
    *,
    operation: str,
    modules: list[Any],
) -> None:
    """migrationを同期接続で流す。"""
    with Operations.context(MigrationContext.configure(connection=connection)):
        for module in modules:
            getattr(module, operation)()


def _prepare_preceding_schema(connection: Connection) -> tuple[list[Any], Any]:
    """0007までのスキーマを作り、0008を返す。"""
    schema.metadata.drop_all(connection, checkfirst=True)
    modules = ordered_migrations()
    target = next(
        module for module in modules if str(module.revision) == _TARGET_REVISION
    )
    preceding = modules[: modules.index(target)]
    _run_revision(connection, operation="upgrade", modules=preceding)
    return modules, target


@pytest.mark.asyncio
async def test_tc44_0008前進migrationが既存薬歴を保持して初回として補完する(
    engine: AsyncEngine,
) -> None:
    """旧payloadと指導日時、状態、versionを維持して新検索列を追加する。"""
    record = finalize_record_with_review(
        create_record(
            profile_updates=ProfileUpdateIntents(
                new_allergies=(create_allergy_intent(),)
            )
        )
    )
    old_values = _old_row_values(record)
    raw_payload = old_values["payload"]
    assert isinstance(raw_payload, dict)
    old_payload = dict(raw_payload)
    assert record.counseled_at is not None
    expected_counseled_at = record.counseled_at.value

    async with engine.connect() as connection:
        transaction = await connection.begin()
        try:

            def migrate(sync_connection: Connection) -> None:
                modules, target = _prepare_preceding_schema(sync_connection)
                sync_connection.execute(
                    insert(schema.medication_history_records).values(**old_values)
                )
                _run_revision(
                    sync_connection,
                    operation="upgrade",
                    modules=[target],
                )
                row = (
                    sync_connection.execute(
                        text(
                            "SELECT record_kind, source_record_id, status, counseled_at, "
                            "payload, version FROM medication_history_records WHERE id = :id"
                        ),
                        {"id": record.id.value},
                    )
                    .mappings()
                    .one()
                )
                assert row["record_kind"] == "initial"
                assert row["source_record_id"] is None
                assert row["status"] == "finalized"
                assert row["counseled_at"] == expected_counseled_at
                assert row["payload"] == old_payload
                assert row["version"] == 4
                assert modules[-1] is target

                constraint_names = {
                    item[0]
                    for item in sync_connection.execute(
                        text(
                            "SELECT conname FROM pg_constraint WHERE conrelid = "
                            "'medication_history_records'::regclass"
                        )
                    )
                }
                assert (
                    "fk_medication_history_records_source_identity" in constraint_names
                )
                assert (
                    "ck_medication_history_records_record_kind_source"
                    in constraint_names
                )
                indexdef = sync_connection.execute(
                    text("SELECT indexdef FROM pg_indexes WHERE indexname = :name"),
                    {"name": "uq_medication_history_records_finalized_dispensing"},
                ).scalar_one()
                assert "(record_kind)::text = 'initial'::text" in str(indexdef)

            await connection.run_sync(migrate)
        finally:
            await transaction.rollback()


@pytest.mark.asyncio
async def test_tc45_0008後退migrationはフォローアップを保護し初回だけなら戻せる(
    engine: AsyncEngine,
) -> None:
    """フォローアップが残る場合は拒否し、除去後の旧スキーマ移行は成功する。"""
    source = finalize_record_with_review(create_record())
    follow_up = create_independent_follow_up_record(source)

    async with engine.connect() as connection:
        transaction = await connection.begin()
        try:

            def migrate_and_downgrade(sync_connection: Connection) -> None:
                _, target = _prepare_preceding_schema(sync_connection)
                sync_connection.execute(
                    insert(schema.medication_history_records).values(
                        **_old_row_values(source)
                    )
                )
                _run_revision(sync_connection, operation="upgrade", modules=[target])
                follow_up_values = MEDICATION_HISTORY_RECORD_MAPPING.row_values(
                    follow_up
                )
                now = datetime(2026, 9, 20, tzinfo=UTC)
                follow_up_values.update(version=1, created_at=now, updated_at=now)
                sync_connection.execute(
                    insert(schema.medication_history_records).values(**follow_up_values)
                )

                with (
                    Operations.context(
                        MigrationContext.configure(connection=sync_connection)
                    ),
                    pytest.raises(RuntimeError, match="フォローアップ薬歴"),
                ):
                    target.downgrade()
                count = sync_connection.execute(
                    text(
                        "SELECT count(*) FROM medication_history_records WHERE id = :id"
                    ),
                    {"id": follow_up.id.value},
                ).scalar_one()
                assert count == 1

                sync_connection.execute(
                    delete(schema.medication_history_records).where(
                        schema.medication_history_records.c.id == follow_up.id.value
                    )
                )
                with Operations.context(
                    MigrationContext.configure(connection=sync_connection)
                ):
                    target.downgrade()
                columns = {
                    item[0]
                    for item in sync_connection.execute(
                        text(
                            "SELECT column_name FROM information_schema.columns "
                            "WHERE table_name = 'medication_history_records'"
                        )
                    )
                }
                assert "record_kind" not in columns
                assert "source_record_id" not in columns

            await connection.run_sync(migrate_and_downgrade)
        finally:
            await transaction.rollback()


async def test_tc45_オフラインdowngradeの生成SQLは行状態を検査して参照鎖を保つ(
    engine: AsyncEngine,
) -> None:
    """生成したSQLでもフォローアップ行があれば参照鎖の削除を止める。"""
    target = next(
        module
        for module in ordered_migrations()
        if str(module.revision) == _TARGET_REVISION
    )
    output = StringIO()
    context = MigrationContext.configure(
        url="postgresql://",
        opts={"as_sql": True, "output_buffer": output},
    )

    with Operations.context(context):
        target.downgrade()

    generated = output.getvalue()
    guard = (
        "IF EXISTS (SELECT 1 FROM medication_history_records "
        "WHERE record_kind = 'follow_up')"
    )
    assert guard in generated
    assert "RAISE EXCEPTION" in generated
    assert generated.index(guard) < generated.index(
        "ALTER TABLE medication_history_records DROP COLUMN source_record_id"
    )
    guard_statement = re.search(r"(?is)DO \$\$.*?\$\$;", generated)
    assert guard_statement is not None

    async with engine.begin() as connection:
        await connection.exec_driver_sql(
            "CREATE TEMP TABLE medication_history_records (record_kind text) "
            "ON COMMIT DROP"
        )
        await connection.exec_driver_sql(
            "INSERT INTO medication_history_records VALUES ('follow_up')"
        )
        savepoint = await connection.begin_nested()
        guard_error: DBAPIError | None = None
        try:
            await connection.exec_driver_sql(guard_statement.group())
        except DBAPIError as error:
            guard_error = error
        finally:
            await savepoint.rollback()

        assert guard_error is not None
        assert "フォローアップ薬歴" in str(guard_error)
        count = await connection.scalar(
            text("SELECT count(*) FROM medication_history_records")
        )
        assert count == 1
