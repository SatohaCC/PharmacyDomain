"""閉局・管理薬剤師の在任と新規業務の保存を、本番の保存境界で検証する。"""

import asyncio
from dataclasses import replace
from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.application.store.management import (
    ChangeStoreStatusCommand,
    RevokeStoreClosureCommand,
)
from app.domain.foundation.exceptions import DomainError
from app.domain.store.lifecycle import StoreStatus
from app.domain.store.manager_assignment import ManagerAbsenceConflictError
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.infrastructure.postgres.repositories.repository_set import (
    PostgresRepositorySet,
)
from tests.factories.dispensing_factory import create_dispensing
from tests.factories.prescription_factory import create_prescription
from tests.integration.organization_helpers import appoint_manager, setup_organization


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["prescription", "dispensing"])
async def test_閉局と新規業務が競合しても閉局店舗に未完了業務を作らない(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession], kind: str
) -> None:
    fixture = await setup_organization(engine, session_factory)
    # 在任していないと保存側が常に拒否され、競合を確かめないまま緑になる。
    await appoint_manager(session_factory, fixture)
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


@pytest.mark.asyncio
async def test_管理薬剤師が不在の店舗では新規業務を保存できない(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """任命が1件も無い店舗を、有効なまま新規業務から締め出す。

    店舗状態だけを見ていた頃は、任命の切れた店舗でも受付から調剤まで通っていた。
    """
    fixture = await setup_organization(engine, session_factory)

    with pytest.raises(ManagerAbsenceConflictError):
        async with fixture.root.request_scope(
            authorization=fixture.authorization
        ) as scope:
            await scope.repositories.prescription.save(
                replace(
                    create_prescription(corporate_id=fixture.corporate.id),
                    store_id=fixture.store.id,
                )
            )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("ends_on", "allowed"),
    [(date(2026, 9, 17), True), (date(2026, 9, 16), False)],
    ids=["業務日が任命の最終日", "前日で任命が終わっている"],
)
async def test_在任の判定は任命の終了日を含む(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    ends_on: date,
    allowed: bool,
) -> None:
    """業務日は ``setup_organization`` の時計が決める 2026-09-17。

    任命期間は終了日を含む閉区間なので、最終日当日はまだ在任している。この
    境界は ``daterange`` をどの向きで作るかに依存し、半開区間で保存すると
    最終日の受付だけが拒否される。演算子と境界の扱いはサーバが決めるため、
    インメモリのダブルでは再現しない。
    """
    fixture = await setup_organization(engine, session_factory)
    await appoint_manager(session_factory, fixture, ends_on=ends_on)

    async def save() -> None:
        async with fixture.root.request_scope(
            authorization=fixture.authorization
        ) as scope:
            await scope.repositories.prescription.save(
                replace(
                    create_prescription(corporate_id=fixture.corporate.id),
                    store_id=fixture.store.id,
                )
            )

    if allowed:
        await save()
    else:
        with pytest.raises(ManagerAbsenceConflictError):
            await save()


@pytest.mark.asyncio
async def test_閉局を取り消すと休止へ戻り管理薬剤師の任命は復元されない(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """取消は訂正であって再開ではない。

    閉局は任命を当日で終了させる。取消で任命まで戻すと、閉局中に別の店舗の
    管理薬剤師になった人と期間が重なりうるので、状態だけを戻す。
    """
    # Arrange
    fixture = await setup_organization(engine, session_factory)
    appointed = await appoint_manager(session_factory, fixture)
    async with fixture.root.request_scope(authorization=fixture.authorization) as scope:
        await scope.use_cases.store.change_status.execute(
            ChangeStoreStatusCommand(
                corporate_id=str(fixture.corporate.id.value),
                store_id=str(fixture.store.id.value),
                status=StoreStatus.CLOSED,
                reason="営業終了",
            )
        )

    # Act
    async with fixture.root.request_scope(authorization=fixture.authorization) as scope:
        revoked = await scope.use_cases.store.revoke_closure.execute(
            RevokeStoreClosureCommand(
                corporate_id=str(fixture.corporate.id.value),
                store_id=str(fixture.store.id.value),
                reason="閉局の操作誤り",
            )
        )

    # Assert
    assert revoked.status == StoreStatus.SUSPENDED
    async with PostgresUnitOfWork(session_factory) as work:
        assignment = await PostgresRepositorySet.create(work).manager_assignment.get(
            appointed.id
        )
    assert assignment is not None
    assert assignment.period.ends_on == date(2026, 9, 17)
