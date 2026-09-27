"""業務Event向けmigrationの標準定義を実PostgreSQLで検証する。"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.domain.care_event.event import Event
from app.domain.care_event.primitives import (
    EventCreatedTimestamp,
    EventOccurredTimestamp,
)
from app.infrastructure.postgres import schema
from app.infrastructure.postgres.connection import PostgresSettings, PostgresUnitOfWork
from app.infrastructure.postgres.repositories.repository_set import (
    PostgresRepositorySet,
)
from tests.factories.persistence_factory import create_patient
from tests.factories.store_factory import create_store
from tests.infrastructure.postgres.helpers import create_corporate

_ROOT = Path(__file__).resolve().parents[2]


async def _run_alembic(database_url: str, *arguments: str) -> str:
    """テスト用URLでAlembic CLIを実行し、失敗時は標準出力を返す。"""
    environment = {**os.environ, "DATABASE_URL": database_url}
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "alembic",
        *arguments,
        cwd=_ROOT,
        env=environment,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    output = (stdout + stderr).decode(errors="replace")
    assert process.returncode == 0, output
    return output


async def test_tc45_01_migrationが有効な標準イベント種別を6件登録する(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    table = schema.metadata.tables.get("event_definitions")
    assert table is not None, "Event種別テーブルが未定義"
    assert {"corporate_id", "standard_code", "is_active"} <= set(table.c.keys())

    async with session_factory() as session:
        result = await session.execute(
            select(table.c.standard_code, table.c.name, table.c.is_active).where(
                table.c.corporate_id.is_(None)
            )
        )
        rows = result.all()

    expected_names = {
        "prescription_reception": "処方箋受付",
        "medication_period_follow_up": "服薬期間中フォローアップ",
        "telephone_follow_up": "電話フォローアップ",
        "in_person_consultation": "来局相談",
        "home_visit": "在宅訪問",
        "online_medication_guidance": "オンライン服薬指導",
    }
    codes = {row.standard_code for row in rows}
    assert codes == set(expected_names)
    assert all(code for code in codes)
    assert all(row.is_active for row in rows)
    assert {row.standard_code: row.name for row in rows} == expected_names


async def test_tc45_56_Alembicの成功済みmigration再実行はデータを変えない(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    postgres_settings: PostgresSettings,
) -> None:
    """head適用後のupgrade再実行が版管理でno-opとなりEventを重複させない。"""
    corporate = create_corporate("Alembic再実行検証")
    store = create_store(corporate_id=corporate.id)
    patient = create_patient(corporate_id=corporate.id)
    occurred_at = datetime(2026, 9, 26, 3, tzinfo=UTC)
    async with PostgresUnitOfWork(session_factory) as work:
        repositories = PostgresRepositorySet.create(work)
        await repositories.corporate.save(corporate)
        await repositories.store.save(store)
        await repositories.patient.save(patient)
        definitions = await repositories.event_definition.list_for_corporate(
            corporate_id=corporate.id
        )
        standard = next(item for item in definitions if item.corporate_id is None)
        event = Event.create(
            event_type_id=standard.id,
            event_type_standard_code=standard.standard_code,
            event_type_name=standard.name,
            corporate_id=corporate.id,
            store_id=store.id,
            patient_id=patient.id,
            occurred_at=EventOccurredTimestamp(occurred_at),
            created_at=EventCreatedTimestamp(occurred_at),
        )
        await repositories.event.save(event)
        await work.commit()

    async with engine.begin() as connection:
        await connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
        before = (
            await connection.execute(
                text(
                    "SELECT (SELECT count(*) FROM care_events WHERE corporate_id = :id), "
                    "(SELECT count(*) FROM event_definitions), "
                    "(SELECT id FROM care_events WHERE id = :event_id)"
                ),
                {"id": corporate.id.value, "event_id": event.id.value},
            )
        ).one()

    try:
        await _run_alembic(postgres_settings.database_url, "stamp", "head")
        await _run_alembic(postgres_settings.database_url, "upgrade", "head")
        await _run_alembic(postgres_settings.database_url, "upgrade", "head")
        current = await _run_alembic(postgres_settings.database_url, "current")
        assert "20260927_0011" in current
        async with engine.connect() as connection:
            after = (
                await connection.execute(
                    text(
                        "SELECT (SELECT count(*) FROM care_events WHERE corporate_id = :id), "
                        "(SELECT count(*) FROM event_definitions), "
                        "(SELECT id FROM care_events WHERE id = :event_id)"
                    ),
                    {"id": corporate.id.value, "event_id": event.id.value},
                )
            ).one()
        assert after == before
    finally:
        async with engine.begin() as connection:
            await connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
