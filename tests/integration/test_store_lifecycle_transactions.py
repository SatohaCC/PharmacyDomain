"""閉局と新規業務保存の競合を本番の保存境界で検証する。"""

import asyncio
from dataclasses import replace

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.application.store.management import ChangeStoreStatusCommand
from app.domain.foundation.exceptions import DomainError
from app.domain.store.lifecycle import StoreStatus
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.infrastructure.postgres.repositories import PostgresRepositorySet
from tests.factories.dispensing_factory import create_dispensing
from tests.factories.prescription_factory import create_prescription
from tests.integration.organization_helpers import setup_organization


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["prescription", "dispensing"])
async def test_閉局と新規業務が競合しても閉局店舗に未完了業務を作らない(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession], kind: str
) -> None:
    fixture = await setup_organization(engine, session_factory)
    barrier = asyncio.Barrier(2)

    async def close() -> None:
        async with fixture.root.request_scope(
            authorization=fixture.authorization
        ) as scope:
            await barrier.wait()
            await scope.use_cases.store.change_status.execute(
                ChangeStoreStatusCommand(
                    corporate_id=str(fixture.corporate.id.value),
                    store_id=str(fixture.store.id.value),
                    status=StoreStatus.CLOSED,
                    reason="営業終了",
                )
            )

    async def start() -> None:
        async with fixture.root.request_scope(
            authorization=fixture.authorization
        ) as scope:
            await barrier.wait()
            if kind == "prescription":
                await scope.repositories.prescription.save(
                    replace(
                        create_prescription(corporate_id=fixture.corporate.id),
                        store_id=fixture.store.id,
                    )
                )
            else:
                await scope.repositories.dispensing.save(
                    replace(
                        create_dispensing(corporate_id=fixture.corporate.id),
                        store_id=fixture.store.id,
                    )
                )

    results = await asyncio.wait_for(
        asyncio.gather(close(), start(), return_exceptions=True), timeout=15
    )
    assert sum(item is None for item in results) == 1
    assert sum(isinstance(item, DomainError) for item in results) == 1
    async with PostgresUnitOfWork(session_factory) as work:
        repos = PostgresRepositorySet.create(work)
        store = await repos.store.get(fixture.store.id)
        from app.infrastructure.postgres.organization import PostgresStoreWorkBoundary

        unfinished = await PostgresStoreWorkBoundary(work).has_unfinished(
            fixture.corporate.id, fixture.store.id
        )
    assert store is not None
    assert not (store.status == StoreStatus.CLOSED and unfinished)
