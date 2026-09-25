"""管理薬剤師の期間競合、交代、スタッフ変更の原子性。"""

import asyncio
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.application.staff.update_qualifications import UpdateStaffQualificationsCommand
from app.application.store.management import ManagerAction, ManageStoreManagerCommand
from app.domain.foundation.exceptions import DomainError
from app.domain.identity.staff_person_link import StaffPersonLink
from app.domain.store.manager_assignment import (
    ManagerAssignmentPeriod,
    ManagerPersonUnresolvedError,
    StoreManagerAssignment,
    StoreManagerAssignmentId,
)
from app.domain.store.manager_repository import (
    ManagerAssignmentConflictError,
    ManagerExclusiveDutyConflictError,
)
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.infrastructure.postgres.repositories.repository_set import (
    PostgresRepositorySet,
)
from tests.factories.staff_factory import create_staff
from tests.factories.store_factory import create_store
from tests.infrastructure.postgres.helpers import create_corporate
from tests.integration.organization_helpers import setup_organization


@pytest.mark.asyncio
@pytest.mark.parametrize("reject_new", [False, True])
async def test_管理薬剤師交代の保存失敗は旧任命の終了も巻き戻す(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    reject_new: bool,
) -> None:
    fixture = await setup_organization(engine, session_factory)
    async with fixture.root.request_scope(authorization=fixture.authorization) as scope:
        old = await scope.use_cases.store.manage_manager.execute(
            ManageStoreManagerCommand(
                corporate_id=str(fixture.corporate.id.value),
                store_id=str(fixture.store.id.value),
                staff_id=str(fixture.staff[0].id.value),
                action=ManagerAction.APPOINT,
                starts_on=date(2026, 9, 1),
            )
        )
    if reject_new:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "ALTER TABLE store_manager_assignments ADD CONSTRAINT test_manager_staff CHECK (staff_id <> '"
                    + str(fixture.staff[1].id.value)
                    + "'::uuid)"
                )
            )
    caught = None
    try:
        async with fixture.root.request_scope(
            authorization=fixture.authorization
        ) as scope:
            await scope.use_cases.store.manage_manager.execute(
                ManageStoreManagerCommand(
                    corporate_id=str(fixture.corporate.id.value),
                    store_id=str(fixture.store.id.value),
                    assignment_id=old.id,
                    staff_id=str(fixture.staff[1].id.value),
                    action=ManagerAction.REPLACE,
                    starts_on=date(2026, 9, 20),
                )
            )
    except Exception as error:
        caught = error
    finally:
        if reject_new:
            async with engine.begin() as connection:
                await connection.execute(
                    text(
                        "ALTER TABLE store_manager_assignments DROP CONSTRAINT test_manager_staff"
                    )
                )
    async with PostgresUnitOfWork(session_factory) as work:
        items = await PostgresRepositorySet.create(
            work
        ).manager_assignment.list_by_store(fixture.corporate.id, fixture.store.id)
    assert len(items) == (1 if reject_new else 2)
    original = next(item for item in items if str(item.id.value) == old.id)
    assert original.period.ends_on == (None if reject_new else date(2026, 9, 19))
    assert (caught is not None) == reject_new
    if not reject_new:
        assert [
            item.staff_id for item in items if item.is_effective_on(date(2026, 9, 20))
        ] == [fixture.staff[1].id]


@pytest.mark.asyncio
async def test_同じ店舗への同時任命はDB排他制約で一件だけ確定する(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    fixture = await setup_organization(engine, session_factory)
    barrier = asyncio.Barrier(2)

    async def appoint(index: int) -> None:
        assignment = StoreManagerAssignment(
            id=StoreManagerAssignmentId.generate(),
            corporate_id=fixture.corporate.id,
            store_id=fixture.store.id,
            staff_id=fixture.staff[index].id,
            person_id=fixture.accounts[index].person_id,
            period=ManagerAssignmentPeriod(starts_on=date(2026, 9, 1)),
        )
        async with PostgresUnitOfWork(session_factory) as work:
            await barrier.wait()
            await PostgresRepositorySet.create(work).manager_assignment.save(assignment)
            await work.commit()

    results = await asyncio.wait_for(
        asyncio.gather(appoint(0), appoint(1), return_exceptions=True), timeout=15
    )
    assert sum(item is None for item in results) == 1
    assert (
        sum(isinstance(item, ManagerAssignmentConflictError) for item in results) == 1
    )


@pytest.mark.asyncio
async def test_薬剤師資格削除と任命が競合しても矛盾した任命を残さない(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    fixture = await setup_organization(engine, session_factory)
    barrier = asyncio.Barrier(2)

    async def appoint() -> None:
        async with fixture.root.request_scope(
            authorization=fixture.authorization
        ) as scope:
            await barrier.wait()
            await scope.use_cases.store.manage_manager.execute(
                ManageStoreManagerCommand(
                    corporate_id=str(fixture.corporate.id.value),
                    store_id=str(fixture.store.id.value),
                    staff_id=str(fixture.staff[0].id.value),
                    action=ManagerAction.APPOINT,
                    starts_on=date(2026, 9, 17),
                )
            )

    async def remove() -> None:
        async with fixture.root.request_scope(
            authorization=fixture.authorization
        ) as scope:
            await barrier.wait()
            await scope.use_cases.staff.update_qualifications.execute(
                UpdateStaffQualificationsCommand(
                    corporate_id=str(fixture.corporate.id.value),
                    staff_id=str(fixture.staff[0].id.value),
                )
            )

    results = await asyncio.wait_for(
        asyncio.gather(appoint(), remove(), return_exceptions=True), timeout=15
    )
    assert sum(item is None for item in results) == 1
    assert sum(isinstance(item, DomainError) for item in results) == 1
    async with PostgresUnitOfWork(session_factory) as work:
        repos = PostgresRepositorySet.create(work)
        staff = await repos.staff.get(
            corporate_id=fixture.corporate.id, staff_id=fixture.staff[0].id
        )
        assignments = await repos.manager_assignment.list_by_store(
            fixture.corporate.id, fixture.store.id
        )
    assert staff is not None
    assert staff.is_pharmacist == bool(assignments)


@pytest.mark.asyncio
async def test_同じ人物は別法人の店舗の管理薬剤師を兼ねられない(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """専任義務は自然人にかかるので、法人が違っても止める。

    排他制約の鍵を法人内のスタッフIDにしていた頃は、グループ内の別法人で
    同じ人物がそれぞれ管理薬剤師になれた。スタッフIDが違うので制約が当たらず、
    例外も出なかった。法人IDを鍵に含めてはならないことを実物で固定する。
    """
    # Arrange
    fixture = await setup_organization(engine, session_factory)
    person_id = fixture.accounts[0].person_id
    other_corporate = create_corporate("グループ内の別法人")
    other_store = create_store(corporate_id=other_corporate.id)
    other_staff = create_staff(corporate_id=other_corporate.id)
    async with PostgresUnitOfWork(session_factory) as work:
        repos = PostgresRepositorySet.create(work)
        await repos.corporate.save(other_corporate)
        await repos.store.save(other_store)
        await repos.staff.save(other_staff)
        await repos.staff_person_link.save(
            StaffPersonLink(
                id=other_staff.id,
                corporate_id=other_corporate.id,
                person_id=person_id,
            )
        )
        await repos.manager_assignment.save(
            StoreManagerAssignment(
                id=StoreManagerAssignmentId.generate(),
                corporate_id=fixture.corporate.id,
                store_id=fixture.store.id,
                staff_id=fixture.staff[0].id,
                person_id=person_id,
                period=ManagerAssignmentPeriod(starts_on=date(2026, 9, 1)),
            )
        )
        await work.commit()

    # Act & Assert
    with pytest.raises(ManagerExclusiveDutyConflictError):
        async with PostgresUnitOfWork(session_factory) as work:
            await PostgresRepositorySet.create(work).manager_assignment.save(
                StoreManagerAssignment(
                    id=StoreManagerAssignmentId.generate(),
                    corporate_id=other_corporate.id,
                    store_id=other_store.id,
                    staff_id=other_staff.id,
                    person_id=person_id,
                    period=ManagerAssignmentPeriod(starts_on=date(2026, 9, 10)),
                )
            )
            await work.commit()


@pytest.mark.asyncio
async def test_本人の対応が無いスタッフは任命として保存できない(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """ユースケースを通さない経路でも、複合外部キーが最後に止める。

    任命の ``person_id`` は対応の写しなので、対応と組で参照させる。こうすると
    「対応の無いスタッフ」も「対応とずれた本人」も同じ制約で弾ける。
    """
    # Arrange
    fixture = await setup_organization(engine, session_factory)
    unlinked = create_staff(corporate_id=fixture.corporate.id)
    async with PostgresUnitOfWork(session_factory) as work:
        await PostgresRepositorySet.create(work).staff.save(unlinked)
        await work.commit()

    # Act & Assert
    with pytest.raises(ManagerPersonUnresolvedError):
        async with PostgresUnitOfWork(session_factory) as work:
            await PostgresRepositorySet.create(work).manager_assignment.save(
                StoreManagerAssignment(
                    id=StoreManagerAssignmentId.generate(),
                    corporate_id=fixture.corporate.id,
                    store_id=fixture.store.id,
                    staff_id=unlinked.id,
                    person_id=fixture.accounts[0].person_id,
                    period=ManagerAssignmentPeriod(starts_on=date(2026, 9, 1)),
                )
            )
            await work.commit()
