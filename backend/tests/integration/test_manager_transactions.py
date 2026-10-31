"""管理薬剤師の期間競合、交代、スタッフ変更の原子性。"""

import asyncio
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.application.staff.commands.deactivate_staff import DeactivateStaffCommand
from app.application.staff.commands.update_staff_qualifications import (
    UpdateStaffQualificationsCommand,
)
from app.application.store.commands.manage_store_manager import (
    ManageStoreManagerCommand,
)
from app.application.store.commands.models import ManagerAction
from app.domain.foundation.exceptions import DomainError
from app.domain.identity.entities import StaffPersonLink
from app.domain.store.entities import StoreManagerAssignment
from app.domain.store.exceptions import (
    ManagerAssignmentConflictError,
    ManagerExclusiveDutyConflictError,
    ManagerPersonUnresolvedError,
)
from app.domain.store.identifiers import StoreManagerAssignmentId
from app.domain.store.value_objects import ManagerAssignmentPeriod
from app.infrastructure.di.repositories import (
    PostgresRepositorySet,
)
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from tests.factories.staff_factory import create_staff
from tests.factories.store_factory import create_store
from tests.infrastructure.postgres.helpers import create_corporate
from tests.integration.organization_helpers import setup_organization
from tests.integration.test_identity_persistence import _person


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
async def test_TC061_法人内本人排他_同法人で同人物が複数店舗に重複任命されるとDB排他制約で拒否する(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """同一法人内で同一人物（person_id）が異なる店舗で重複する期間に管理薬剤師になることは
    専任義務違反であり、ex_manager_person_period 排他制約で拒否される。
    非重複期間の任命は同一人物でも保存できる。
    """
    # Arrange
    fixture = await setup_organization(engine, session_factory)
    person_id = fixture.accounts[0].person_id
    store2 = create_store(corporate_id=fixture.corporate.id, name="第二店舗")
    staff2 = create_staff(corporate_id=fixture.corporate.id)
    async with PostgresUnitOfWork(session_factory) as work:
        repos = PostgresRepositorySet.create(work)
        await repos.store.save(store2)
        await repos.staff.save(staff2)
        await repos.staff_person_link.save(
            StaffPersonLink(
                id=staff2.id,
                corporate_id=fixture.corporate.id,
                person_id=person_id,
            )
        )
        # 店舗1の管理薬剤師として 2026-09-01 〜 2026-09-20 まで任命
        await repos.manager_assignment.save(
            StoreManagerAssignment(
                id=StoreManagerAssignmentId.generate(),
                corporate_id=fixture.corporate.id,
                store_id=fixture.store.id,
                staff_id=fixture.staff[0].id,
                person_id=person_id,
                period=ManagerAssignmentPeriod(
                    starts_on=date(2026, 9, 1), ends_on=date(2026, 9, 20)
                ),
            )
        )
        await work.commit()

    # Act & Assert: 重複する期間（2026-09-10 〜）で店舗2への任命は拒否される
    with pytest.raises(ManagerExclusiveDutyConflictError):
        async with PostgresUnitOfWork(session_factory) as work:
            await PostgresRepositorySet.create(work).manager_assignment.save(
                StoreManagerAssignment(
                    id=StoreManagerAssignmentId.generate(),
                    corporate_id=fixture.corporate.id,
                    store_id=store2.id,
                    staff_id=staff2.id,
                    person_id=person_id,
                    period=ManagerAssignmentPeriod(starts_on=date(2026, 9, 10)),
                )
            )
            await work.commit()

    # 非重複期間（2026-09-21 〜）なら同じ人物でも任命できる
    async with PostgresUnitOfWork(session_factory) as work:
        await PostgresRepositorySet.create(work).manager_assignment.save(
            StoreManagerAssignment(
                id=StoreManagerAssignmentId.generate(),
                corporate_id=fixture.corporate.id,
                store_id=store2.id,
                staff_id=staff2.id,
                person_id=person_id,
                period=ManagerAssignmentPeriod(starts_on=date(2026, 9, 21)),
            )
        )
        await work.commit()


@pytest.mark.asyncio
async def test_TC062_法人間任命_独立_各法人の独立した本人は同期間に任命できる(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """各法人の本人は独立しており、法人Aと法人Bでそれぞれ同期間に管理薬剤師が任命されても
    法人横断の排他はかからず、独立して成功する。
    """
    # Arrange
    fixture = await setup_organization(engine, session_factory)
    corp_b = create_corporate("別法人B")
    store_b = create_store(corporate_id=corp_b.id, name="B店")
    person_b = _person(corporate_id=corp_b.id)
    staff_b = create_staff(corporate_id=corp_b.id)

    async with PostgresUnitOfWork(session_factory) as work:
        repos = PostgresRepositorySet.create(work)
        await repos.corporate.save(corp_b)
        await repos.store.save(store_b)
        await repos.account_person.save(person_b)
        await repos.staff.save(staff_b)
        await repos.staff_person_link.save(
            StaffPersonLink(
                id=staff_b.id,
                corporate_id=corp_b.id,
                person_id=person_b.id,
            )
        )
        # 法人Aの任命（2026-09-01 〜）
        await repos.manager_assignment.save(
            StoreManagerAssignment(
                id=StoreManagerAssignmentId.generate(),
                corporate_id=fixture.corporate.id,
                store_id=fixture.store.id,
                staff_id=fixture.staff[0].id,
                person_id=fixture.accounts[0].person_id,
                period=ManagerAssignmentPeriod(starts_on=date(2026, 9, 1)),
            )
        )
        # 法人Bの任命（同期間 2026-09-01 〜）
        await repos.manager_assignment.save(
            StoreManagerAssignment(
                id=StoreManagerAssignmentId.generate(),
                corporate_id=corp_b.id,
                store_id=store_b.id,
                staff_id=staff_b.id,
                person_id=person_b.id,
                period=ManagerAssignmentPeriod(starts_on=date(2026, 9, 1)),
            )
        )
        await work.commit()

    # Assert: 両法人の任命がそれぞれ保存されている
    async with PostgresUnitOfWork(session_factory) as work:
        repos = PostgresRepositorySet.create(work)
        assignments_a = await repos.manager_assignment.list_by_store(
            fixture.corporate.id, fixture.store.id
        )
        assignments_b = await repos.manager_assignment.list_by_store(
            corp_b.id, store_b.id
        )
    assert len(assignments_a) == 1
    assert len(assignments_b) == 1


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


@pytest.mark.asyncio
async def test_TC063_任命対退職_並行競合でも不整合な組み合わせを残さない(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """管理薬剤師の任命追加と退職が並行して実行された場合、
    退職先行なら無効スタッフの任命が拒否され、任命先行なら在任中退職が拒否される。
    どちらの順序でも「無効スタッフが管理薬剤師に任命されている」不整合は残らない。
    """
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

    async def retire() -> None:
        async with fixture.root.request_scope(
            authorization=fixture.authorization
        ) as scope:
            await barrier.wait()
            await scope.use_cases.staff.deactivate.execute(
                DeactivateStaffCommand(
                    corporate_id=str(fixture.corporate.id.value),
                    staff_id=str(fixture.staff[0].id.value),
                    retired_on=date(2026, 9, 17),
                )
            )

    results = await asyncio.wait_for(
        asyncio.gather(appoint(), retire(), return_exceptions=True), timeout=15
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
    # 任命が存在するならスタッフは有効であり、スタッフが無効なら任命は存在しない
    assert staff.is_active == bool(assignments)
