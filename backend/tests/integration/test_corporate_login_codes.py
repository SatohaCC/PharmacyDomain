"""法人コードの同時発行・DB制約・保存復元を実DBで確認する。"""

import asyncio
import importlib
from dataclasses import replace

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.domain.corporate.primitives import CorporateLoginCode
from app.infrastructure.corporate.postgres.corporate import PostgresCorporateRepository
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from tests.infrastructure.postgres.helpers import create_corporate


@pytest.mark.asyncio
async def test_法人コード_同時発行しても_異なる六桁で保存復元できる(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    async def register(number: int) -> str:
        async with PostgresUnitOfWork(session_factory) as work:
            repository = PostgresCorporateRepository(work)
            code = await repository.allocate_login_code()
            corporate = replace(
                create_corporate(f"法人コード検証{number}"),
                login_code=CorporateLoginCode(code),
            )
            await repository.save(corporate)
            await work.commit()
        async with PostgresUnitOfWork(session_factory) as work:
            restored = await PostgresCorporateRepository(work).get(corporate.id)
            assert restored is not None
            assert restored.login_code.value == code
        return code

    codes = await asyncio.gather(*(register(number) for number in range(4)))

    assert len(set(codes)) == 4
    assert all(len(code) == 6 and code.isascii() and code.isdigit() for code in codes)


@pytest.mark.asyncio
async def test_法人コード移行_既存法人のUUIDを保ち_コードを保存復元できる(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    corporate = create_corporate()
    async with PostgresUnitOfWork(session_factory) as work:
        await PostgresCorporateRepository(work).save(corporate)
        await work.commit()

    def migrate(connection: Connection) -> None:
        migration = importlib.import_module(
            "migrations.versions.20261108_0020_corporate_login_code"
        )
        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
            migration.upgrade()

    async with engine.begin() as connection:
        await connection.run_sync(migrate)

    async with PostgresUnitOfWork(session_factory) as work:
        repository = PostgresCorporateRepository(work)
        restored = await repository.get(corporate.id)
        assert restored is not None
        assert restored.id == corporate.id
        assert restored.login_code.value == "000000"
        assert await repository.allocate_login_code() == "000001"
