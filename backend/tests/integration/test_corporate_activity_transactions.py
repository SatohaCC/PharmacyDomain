"""法人停止と通常業務の保存を実PostgreSQLで直列化する検証。"""

import asyncio
from dataclasses import replace

import pytest
from sqlalchemy import column, func, select, table
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.application.corporate.change_corporate_status import (
    ChangeCorporateStatusCommand,
)
from app.application.corporate.exceptions import CorporateInactiveError
from app.domain.staff.primitives import JobTitle
from app.infrastructure.di.repositories import (
    PostgresRepositorySet,
)
from app.infrastructure.di.root import PostgresRequestScope
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from tests.factories.prescription_factory import create_prescription
from tests.factories.store_factory import create_store_names
from tests.integration.organization_helpers import appoint_manager, setup_organization


async def _ロック待機を確認する(engine: AsyncEngine, pid: int) -> None:
    """時間経過ではなく、競合処理がDBのロック待ちに入ったことを確認する。"""
    locks = table("pg_locks", column("pid"), column("locktype"), column("granted"))
    statement = (
        select(func.count())
        .select_from(locks)
        .where(
            locks.c.pid == pid,
            locks.c.locktype == "advisory",
            locks.c.granted.is_(False),
        )
    )
    async with engine.connect() as connection:
        while not await connection.scalar(statement):
            await asyncio.sleep(0.01)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["store", "staff", "prescription"])
@pytest.mark.parametrize("stop_first", [True, False])
async def test_法人停止と通常業務の保存_先行処理が確定するまで待ち_停止後の保存を拒否する(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    kind: str,
    stop_first: bool,
) -> None:
    # Arrange
    fixture = await setup_organization(engine, session_factory)
    await appoint_manager(session_factory, fixture)
    prescription = replace(
        create_prescription(corporate_id=fixture.corporate.id),
        store_id=fixture.store.id,
    )
    changed_store = fixture.store.change_names(create_store_names(name="変更後薬局"))
    changed_staff = fixture.staff[0].change_job_title(JobTitle("主任"))
    pid_ready: asyncio.Future[int] = asyncio.get_running_loop().create_future()

    async def operate(scope: PostgresRequestScope, *, stop: bool) -> None:
        if stop:
            await scope.use_cases.corporate.change_status.execute(
                ChangeCorporateStatusCommand(
                    corporate_id=str(fixture.corporate.id.value), is_active=False
                )
            )
        elif kind == "store":
            await scope.repositories.store.get(fixture.store.id)
            await scope.repositories.store.save(changed_store)
        elif kind == "staff":
            await scope.repositories.staff.get(
                corporate_id=fixture.corporate.id, staff_id=fixture.staff[0].id
            )
            await scope.repositories.staff.save(changed_staff)
        else:
            await scope.repositories.prescription.save(prescription)

    async def competing() -> None:
        async with fixture.root.request_scope(
            authorization=fixture.authorization
        ) as scope:
            pid = await scope.repositories.corporate.session.scalar(
                select(func.pg_backend_pid())
            )
            assert isinstance(pid, int)
            pid_ready.set_result(pid)
            await operate(scope, stop=not stop_first)

    # Act: 先行処理の未確定状態で競合処理を開始し、実際の待機を確認する。
    task: asyncio.Task[None] | None = None
    try:
        async with fixture.root.request_scope(
            authorization=fixture.authorization
        ) as scope:
            await operate(scope, stop=stop_first)
            task = asyncio.create_task(competing())
            pid = await asyncio.wait_for(asyncio.shield(pid_ready), timeout=10)
            await asyncio.wait_for(_ロック待機を確認する(engine, pid), timeout=10)
            assert not task.done()
        if stop_first:
            with pytest.raises(CorporateInactiveError):
                await asyncio.wait_for(task, timeout=10)
        else:
            await asyncio.wait_for(task, timeout=10)
    finally:
        if task is not None:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    # Assert: 停止は必ず確定し、停止に後続した保存は残らない。
    async with PostgresUnitOfWork(session_factory) as work:
        repos = PostgresRepositorySet.create(work)
        corporate = await repos.corporate.get(fixture.corporate.id)
        assert corporate is not None
        assert not corporate.is_active
        if kind == "store":
            store = await repos.store.get(fixture.store.id)
            assert store is not None
            assert store.names == (
                fixture.store.names if stop_first else changed_store.names
            )
        elif kind == "staff":
            staff = await repos.staff.get(
                corporate_id=fixture.corporate.id, staff_id=fixture.staff[0].id
            )
            assert staff is not None
            assert staff.job_title == (
                fixture.staff[0].job_title if stop_first else changed_staff.job_title
            )
        else:
            saved = await repos.prescription.get(
                corporate_id=fixture.corporate.id, prescription_id=prescription.id
            )
            assert (saved is None) == stop_first
