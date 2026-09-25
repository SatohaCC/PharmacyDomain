"""本人・法人アクセス権を並行更新しても追跡と管理者を失わない。"""

import asyncio
from datetime import date, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.application.identity.invite_user import InviteUserCommand
from app.application.identity.resolve_actor import VerifiedSubject
from app.application.staff.deactivate_staff import DeactivateStaffCommand
from app.domain.identity.exceptions import IdentityConflictError
from app.domain.identity.primitives import AccountStatus, MembershipRole
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.infrastructure.postgres.repositories.repository_set import (
    PostgresRepositorySet,
)
from tests.integration.organization_helpers import setup_organization
from tests.integration.test_identity_persistence import _person


@pytest.mark.asyncio
@pytest.mark.parametrize("account_stop", [False, True])
async def test_管理者二人の同時停止でも最後の一人を残す(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    account_stop: bool,
) -> None:
    fixture = await setup_organization(engine, session_factory)
    barrier = asyncio.Barrier(2)

    async def stop(index: int) -> None:
        async with fixture.root.request_scope(
            authorization=fixture.authorization
        ) as scope:
            await barrier.wait()
            if account_stop:
                await scope.use_cases.identity.suspend_account.execute(
                    str(fixture.accounts[index].id.value)
                )
            else:
                await scope.use_cases.identity.change_membership.execute(
                    str(fixture.corporate.id.value),
                    str(fixture.memberships[index].id.value),
                    status=AccountStatus.SUSPENDED,
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
                    retired_on=date(2026, 12, 31),
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
        None if reject_membership else date(2026, 12, 31)
    )
    assert membership.status == (
        AccountStatus.ACTIVE if reject_membership else AccountStatus.SUSPENDED
    )
    assert account.status == AccountStatus.ACTIVE
    assert (caught is not None) == reject_membership


@pytest.mark.asyncio
async def test_同じ招待の同時受諾は一人のアカウントと一つの権限だけを作る(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    fixture = await setup_organization(engine, session_factory)
    person = _person()
    async with fixture.root.request_scope(authorization=fixture.authorization) as scope:
        await scope.repositories.account_person.save(person)
        invitation = await scope.use_cases.identity.invite.execute(
            InviteUserCommand(
                corporate_id=str(fixture.corporate.id.value),
                person_id=str(person.id.value),
                addressee="invited@example.test",
                role=MembershipRole.CORPORATE_ADMIN,
                expires_at=fixture.root.clock.now() + timedelta(days=1),
            )
        )
    barrier = asyncio.Barrier(2)

    async def accept() -> object:
        await barrier.wait()
        return await fixture.root.accept_invitation(
            VerifiedSubject(principal_id="issuer/subject"),
            invitation.secret,
        )

    results = await asyncio.wait_for(
        asyncio.gather(accept(), accept(), return_exceptions=True), timeout=15
    )
    assert sum(isinstance(item, IdentityConflictError) for item in results) == 1
    async with PostgresUnitOfWork(session_factory) as work:
        repos = PostgresRepositorySet.create(work)
        account = await repos.user_account.get_by_person(person.id)
        assert account is not None
        assert await repos.membership.find_active_for_account(account.id) is not None
