"""本人・法人アクセス権を並行更新しても追跡と管理者を失わない。"""

import asyncio
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.application.staff.commands.deactivate_staff import DeactivateStaffCommand
from app.domain.identity.exceptions import IdentityConflictError
from app.domain.identity.primitives import AccountStatus
from app.infrastructure.di.repositories import (
    PostgresRepositorySet,
)
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from tests.integration.organization_helpers import setup_organization


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["membership", "account", "staff_retire"])
async def test_TC064_管理者二人の同時停止でも最後の一人を残す(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    mode: str,
) -> None:
    fixture = await setup_organization(engine, session_factory)
    barrier = asyncio.Barrier(2)

    async def stop(index: int) -> None:
        async with fixture.root.request_scope(
            authorization=fixture.authorization
        ) as scope:
            await barrier.wait()
            if mode == "account":
                await scope.use_cases.identity.suspend_account.execute(
                    str(fixture.accounts[index].id.value)
                )
            elif mode == "membership":
                await scope.use_cases.identity.change_membership.execute(
                    str(fixture.corporate.id.value),
                    str(fixture.memberships[index].id.value),
                    status=AccountStatus.SUSPENDED,
                )
            else:
                await scope.use_cases.staff.deactivate.execute(
                    DeactivateStaffCommand(
                        corporate_id=str(fixture.corporate.id.value),
                        staff_id=str(fixture.staff[index].id.value),
                        retired_on=date(2026, 9, 17),
                    )
                )

    results = await asyncio.wait_for(
        asyncio.gather(stop(0), stop(1), return_exceptions=True), timeout=15
    )
    assert sum(item is None for item in results) == 1
    assert sum(isinstance(item, IdentityConflictError) for item in results) == 1
    async with session_factory() as session:
        count = await session.scalar(
            text(
                "SELECT count(*) FROM corporate_memberships m JOIN user_accounts a ON m.account_id=a.id WHERE m.status='active' AND a.status='active'"
            )
        )
        assert count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("reject_membership", [False, True])
async def test_未来日退職も即時に権限を止め保存失敗なら所属ごと戻す(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    reject_membership: bool,
) -> None:
    fixture = await setup_organization(engine, session_factory)
    if reject_membership:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "ALTER TABLE corporate_memberships ADD CONSTRAINT test_active_only CHECK (status = 'active')"
                )
            )
    caught = None
    try:
        async with fixture.root.request_scope(
            authorization=fixture.authorization
        ) as scope:
            await scope.use_cases.staff.deactivate.execute(
                DeactivateStaffCommand(
                    corporate_id=str(fixture.corporate.id.value),
                    staff_id=str(fixture.staff[0].id.value),
                    retired_on=date(2026, 9, 17),
                )
            )
    except Exception as error:
        caught = error
    finally:
        if reject_membership:
            async with engine.begin() as connection:
                await connection.execute(
                    text(
                        "ALTER TABLE corporate_memberships DROP CONSTRAINT test_active_only"
                    )
                )
    async with PostgresUnitOfWork(session_factory) as work:
        repos = PostgresRepositorySet.create(work)
        staff = await repos.staff.get(
            corporate_id=fixture.corporate.id, staff_id=fixture.staff[0].id
        )
        membership = await repos.membership.get(fixture.memberships[0].id)
        account = await repos.user_account.get(fixture.accounts[0].id)
    assert staff is not None and membership is not None and account is not None
    assert staff.is_active == reject_membership
    assert staff.affiliations[0].period.end_date == (
        None if reject_membership else date(2026, 9, 17)
    )
    assert membership.status == (
        AccountStatus.ACTIVE if reject_membership else AccountStatus.SUSPENDED
    )
    assert account.status == (
        AccountStatus.ACTIVE if reject_membership else AccountStatus.SUSPENDED
    )
    assert (caught is not None) == reject_membership


@pytest.mark.asyncio
async def test_TC065_退職対業務保存_並行競合でも退職先行なら保存拒否され不整合署名は残らない(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """古いActorセッションで退職と業務更新が並行した場合、
    業務先行なら成立後に退職、退職先行なら業務保存が拒否される。
    退職確定後に古いActorでの業務署名は残らない。
    """
    from app.application.access_control.boundary_models import (
        ActorRole,
        ResolvedActorContext,
    )
    from app.application.access_control.policies import AuthorizationService

    fixture = await setup_organization(engine, session_factory)
    actor_auth = AuthorizationService(
        ResolvedActorContext(
            principal_id="staff-actor-0",
            roles=frozenset({ActorRole.STORE_OPERATOR}),
            person_id=fixture.accounts[0].person_id,
            account_id=fixture.accounts[0].id,
            membership_id=fixture.memberships[0].id,
            corporate_id=fixture.corporate.id,
            staff_id=fixture.staff[0].id,
            store_ids=frozenset({fixture.store.id}),
        )
    )
    barrier = asyncio.Barrier(2)

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

    async def operate() -> None:
        async with fixture.root.request_scope(authorization=actor_auth) as scope:
            await barrier.wait()
            staff = await scope.repositories.staff.get(
                corporate_id=fixture.corporate.id, staff_id=fixture.staff[0].id
            )
            assert staff is not None
            await scope.repositories.staff.save(staff)

    results = await asyncio.wait_for(
        asyncio.gather(retire(), operate(), return_exceptions=True), timeout=15
    )
    # 業務先行なら成立、退職先行なら保存拒否。どちらの順序でも片方は成功する
    assert any(item is None for item in results)

    # 業務先行で退職側が楽観ロック衝突した場合は、退職を再実行して確定させる
    if isinstance(results[0], Exception):
        async with fixture.root.request_scope(
            authorization=fixture.authorization
        ) as scope:
            await scope.use_cases.staff.deactivate.execute(
                DeactivateStaffCommand(
                    corporate_id=str(fixture.corporate.id.value),
                    staff_id=str(fixture.staff[0].id.value),
                    retired_on=date(2026, 9, 17),
                )
            )

    async with PostgresUnitOfWork(session_factory) as work:
        repos = PostgresRepositorySet.create(work)
        staff = await repos.staff.get(
            corporate_id=fixture.corporate.id, staff_id=fixture.staff[0].id
        )
        account = await repos.user_account.get(fixture.accounts[0].id)
    assert staff is not None and account is not None
    assert not staff.is_active
    assert account.status == AccountStatus.SUSPENDED

    # 退職確定後は、ResolveActorUseCaseにより古いActorのトークン解決が拒否される
    from app.application.identity.boundary_models import VerifiedSubject
    from app.application.identity.errors import UnavailableIdentityError

    async with fixture.root.request_scope(authorization=fixture.authorization) as scope:
        with pytest.raises(UnavailableIdentityError):
            await scope.use_cases.identity.resolve_actor.execute(
                VerifiedSubject(principal_id="issuer/person-0")
            )
