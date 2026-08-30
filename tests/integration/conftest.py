"""実PostgreSQLへ接続する結合テストの基盤。

DBなしのテストでは、Repositoryが組み立てたSQLの形までしか固定できない。
``ON CONFLICT`` が実際に何行に当たるか、asyncpg が制約名をどう返すか、部分一意
インデックスがどの行を弾くかはサーバの挙動であり、ここで初めて検証できる。

``TEST_DATABASE_URL`` が無い環境では自動でスキップする。既定の品質ゲート
（``uv run pytest -q``）はDB無しで緑のまま保ちつつ、DBがあるときは同じコマンドで
一緒に走る。
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Connection, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.infrastructure.postgres.engine import (
    create_async_engine_from_settings,
    create_session_factory,
)
from app.infrastructure.postgres.schema import metadata
from app.infrastructure.postgres.settings import PostgresSettings
from app.infrastructure.postgres.unit_of_work import PostgresUnitOfWork
from tests.infrastructure.postgres.helpers import ordered_migrations

_DATABASE_URL_KEY = "TEST_DATABASE_URL"
_HERE = Path(__file__).resolve().parent

# スキーマ適用はセッション中1回でよい。テスト間の独立はTRUNCATEで作る。
_schema_applied = False


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """この階層のテストに integration マーカーを自動で付ける。

    各モジュールで付け忘れると、DBを持たないCIジョブで落ちる側へ紛れ込む。
    """
    for item in items:
        path = getattr(item, "path", None)
        if path is not None and _HERE in Path(str(path)).parents:
            item.add_marker(pytest.mark.integration)


@pytest.fixture(scope="session")
def postgres_settings() -> PostgresSettings:
    """テスト用DBの接続設定。未設定なら以降のテストを飛ばす。"""
    raw_url = os.environ.get(_DATABASE_URL_KEY, "").strip()
    if not raw_url:
        pytest.skip(
            f"{_DATABASE_URL_KEY} が未設定のため、実PostgreSQLの結合テストを飛ばす。"
        )
    # 本番と同じ正規化・検証を通す（同期URLもasyncpg用へ揃う）。
    return PostgresSettings.from_environment({"DATABASE_URL": raw_url})


def _apply_migration(connection: Connection) -> None:
    """既存の表を落としてから、マイグレーションでスキーマを作り直す。

    ``metadata.create_all`` ではなくマイグレーションを流すのは、実サーバに対して
    マイグレーションが本当に適用できることを、ここで一緒に確かめるため。
    """
    metadata.drop_all(connection, checkfirst=True)
    context = MigrationContext.configure(connection=connection)
    with Operations.context(context):
        for module in ordered_migrations():
            module.upgrade()


async def _ensure_schema(engine: AsyncEngine) -> None:
    """セッション中で最初の1回だけスキーマを作る。"""
    global _schema_applied
    if _schema_applied:
        return
    async with engine.begin() as connection:
        await connection.run_sync(_apply_migration)
    _schema_applied = True


async def _truncate_all(engine: AsyncEngine) -> None:
    """全テーブルを空にして、テスト間の独立を作る。"""
    table_names = ", ".join(table.name for table in metadata.sorted_tables)
    async with engine.begin() as connection:
        await connection.execute(
            text(f"TRUNCATE {table_names} RESTART IDENTITY CASCADE")
        )


@pytest.fixture
async def engine(postgres_settings: PostgresSettings) -> AsyncIterator[AsyncEngine]:
    """テストごとに空のスキーマを持つ非同期エンジンを渡す。"""
    engine = create_async_engine_from_settings(postgres_settings)
    try:
        await _ensure_schema(engine)
        await _truncate_all(engine)
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """本番と同じ設定のセッションファクトリ。"""
    return create_session_factory(engine)


@pytest.fixture
def unit_of_work(
    session_factory: async_sessionmaker[AsyncSession],
) -> PostgresUnitOfWork:
    """1トランザクション分の Unit of Work。"""
    return PostgresUnitOfWork(session_factory)
