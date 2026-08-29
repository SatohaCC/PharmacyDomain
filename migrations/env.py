"""非同期 PostgreSQL 用 Alembic 環境。"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection

from app.infrastructure.postgres.engine import create_async_engine_from_settings
from app.infrastructure.postgres.schema import metadata
from app.infrastructure.postgres.settings import PostgresSettings

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = metadata


def run_migrations_offline() -> None:
    """接続せずに migration SQL を生成する。"""
    settings = PostgresSettings.from_environment()
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _run_migrations(connection: Connection) -> None:
    """同期接続上で Alembic の migration を実行する。"""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def _run_async_migrations() -> None:
    """非同期エンジンから同期 migration API を呼び出す。"""
    settings = PostgresSettings.from_environment()
    engine = create_async_engine_from_settings(settings)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(_run_migrations)
    finally:
        await engine.dispose()


def run_migrations_online() -> None:
    """PostgreSQL へ接続して migration を適用する。"""
    asyncio.run(_run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
