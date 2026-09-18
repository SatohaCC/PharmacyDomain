"""実業務更新と本人監査の同時確定を検証する。"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.application.access_control.models import ActorRole, ResolvedActorContext
from app.application.access_control.policy import AuthorizationService
from app.application.corporate.register_corporate import RegisterCorporateCommand
from app.domain.identity.primitives import UserAccountId
from app.domain.identity.user_account import UserAccount
from app.infrastructure.di.root import PostgresCompositionRoot
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.infrastructure.postgres.repositories import PostgresRepositorySet
from tests.fakes.fake_clock import FakeClock
from tests.integration.test_identity_persistence import _person


@pytest.mark.asyncio
@pytest.mark.parametrize("audit_failure", [False, True])
async def test_法人登録と実在する本人監査は同時に確定する(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    audit_failure: bool,
) -> None:
    person = _person()
    account = UserAccount(
        id=UserAccountId.generate(), person_id=person.id, is_vendor_admin=True
    )
    async with PostgresUnitOfWork(session_factory) as work:
        repos = PostgresRepositorySet.create(work)
        await repos.account_person.save(person)
        await repos.user_account.save(account)
        await work.commit()
    actor = ResolvedActorContext(
        principal_id="verified",
        roles=frozenset({ActorRole.VENDOR_SYSTEM_ADMIN}),
        person_id=person.id,
        account_id=account.id,
    )
    clock = FakeClock(datetime(2026, 9, 17, tzinfo=UTC))
    root = PostgresCompositionRoot(engine, session_factory, clock)
    if audit_failure:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "ALTER TABLE operation_audits ADD CONSTRAINT test_reject_audit CHECK (false)"
                )
            )
    caught: Exception | None = None
    try:
        async with root.request_scope(
            authorization=AuthorizationService(actor)
        ) as scope:
            await scope.use_cases.corporate.register.execute(
                RegisterCorporateCommand(
                    name="原子的監査法人",
                    representative_last_name="山田",
                    representative_first_name="太郎",
                )
            )
    except Exception as error:
        caught = error
    finally:
        if audit_failure:
            async with engine.begin() as connection:
                await connection.execute(
                    text(
                        "ALTER TABLE operation_audits DROP CONSTRAINT test_reject_audit"
                    )
                )
    async with engine.connect() as connection:
        rows = (
            (
                await connection.execute(
                    text(
                        "SELECT person_id, account_id, resource_id, recorded_at FROM operation_audits"
                    )
                )
            )
            .mappings()
            .all()
        )
        count = (
            await connection.execute(text("SELECT count(*) FROM corporates"))
        ).scalar_one()
    if audit_failure:
        assert caught is not None
        assert count == 0 and not rows
    else:
        assert caught is None
        assert count == 1 and len(rows) == 1
        assert rows[0]["person_id"] == person.id.value
        assert rows[0]["account_id"] == account.id.value
        assert rows[0]["recorded_at"] == clock.now()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE operation_audits SET operation = '改変'",
        "DELETE FROM operation_audits",
        "DELETE FROM user_accounts",
        "DELETE FROM account_people",
    ],
)
async def test_監査と監査が参照する本人を削除できない(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    statement: str,
) -> None:
    from sqlalchemy.exc import IntegrityError

    await test_法人登録と実在する本人監査は同時に確定する(
        engine, session_factory, False
    )
    with pytest.raises(IntegrityError):
        async with engine.begin() as connection:
            await connection.execute(text(statement))
    async with engine.connect() as connection:
        assert (
            await connection.execute(text("SELECT count(*) FROM operation_audits"))
        ).scalar_one() == 1
