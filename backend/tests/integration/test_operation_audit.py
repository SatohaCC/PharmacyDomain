"""実業務更新と本人監査の同時確定を検証する。"""

from dataclasses import replace
from datetime import UTC, datetime, time

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.application.access_control.boundary_models import (
    ActorContext,
    ActorRole,
    ResolvedActorContext,
)
from app.application.access_control.policies import AuthorizationService
from app.application.corporate.commands.models import RegisterCorporateCommand
from app.application.identity.errors import UnavailableIdentityError
from app.application.store.commands.models import (
    BusinessHourSlotInput,
    ChangeStoreBusinessHoursCommand,
    WeekdayBusinessHoursInput,
)
from app.dev_main import build_actor_provider
from app.domain.corporate.identifiers import CorporateId
from app.domain.corporate.primitives import CorporateLoginCode, CorporateName
from app.domain.identity.entities import VendorOperator
from app.domain.identity.identifiers import VendorOperatorId
from app.domain.identity.primitives import (
    CorporateUserEmail,
    ExternalSubjectKey,
    LoginId,
)
from app.domain.store.primitives import BusinessWeekday
from app.infrastructure.di.repositories import (
    PostgresRepositorySet,
)
from app.infrastructure.di.root import PostgresCompositionRoot
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from tests.factories.store_factory import create_store
from tests.fakes.fake_clock import FakeClock
from tools.seed_dev_data import apply_seed, build_seed_data


@pytest.mark.asyncio
async def test_営業時間登録_別法人を操作する開発ベンダー_監査と同時に確定する(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # Arrange
    data = build_seed_data()
    target_corporate = replace(
        data.corporate,
        login_code=CorporateLoginCode("000001"),
        id=CorporateId.generate(),
        name=CorporateName("操作対象の別法人"),
        corporate_number=None,
        invoice_number=None,
    )
    target_store = create_store(corporate_id=target_corporate.id)
    async with PostgresUnitOfWork(session_factory) as work:
        await apply_seed(work, data)
        repositories = PostgresRepositorySet.create(work)
        await repositories.corporate.save(target_corporate)
        await repositories.store.save(target_store)
        await work.commit()
    provider = build_actor_provider(
        {
            "DEV_ACTOR_TOKEN": "開発テスト".encode().hex(),
            "DEV_ACTOR_PERSON_ID": str(data.vendor_person.id.value),
            "DEV_ACTOR_ACCOUNT_ID": str(data.vendor_account.id.value),
            "DEV_ACTOR_OPERATOR_ID": str(data.vendor_operator.id.value),
        }
    )
    actor = await provider.authenticate("開発テスト".encode().hex())
    clock = FakeClock(datetime(2026, 11, 2, tzinfo=UTC))
    root = PostgresCompositionRoot(engine, session_factory, clock)
    weekly = tuple(
        WeekdayBusinessHoursInput(
            weekday=day,
            slots=()
            if day is BusinessWeekday.SUNDAY
            else (BusinessHourSlotInput(opens_at=time(9), closes_at=time(18)),),
        )
        for day in BusinessWeekday
    )

    # Act
    async with root.request_scope(authorization=AuthorizationService(actor)) as scope:
        await scope.use_cases.store.change_business_hours.execute(
            ChangeStoreBusinessHoursCommand(
                corporate_id=str(target_corporate.id.value),
                store_id=str(target_store.id.value),
                weekly=weekly,
            )
        )

    # Assert
    async with PostgresUnitOfWork(session_factory) as work:
        store = await PostgresRepositorySet.create(work).store.get(target_store.id)
        assert store is not None and store.business_hours is not None
        assert len(store.business_hours.weekly) == 7
        audit = (
            await work.session.execute(
                text(
                    "SELECT operator_id, person_id, account_id FROM operation_audits "
                    "WHERE operation = 'stores.update'"
                )
            )
        ).one()
        assert audit.operator_id == data.vendor_operator.id.value
        assert audit.person_id is None
        assert audit.account_id is None


@pytest.mark.asyncio
@pytest.mark.parametrize("audit_failure", [False, True])
async def test_法人登録と実在する本人監査は同時に確定する(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    audit_failure: bool,
) -> None:
    vendor_operator = VendorOperator(
        id=VendorOperatorId.generate(),
        email=CorporateUserEmail("vendor@example.test"),
        login_id=LoginId("vendor-admin"),
        external_subject=ExternalSubjectKey("verified"),
        is_active=True,
    )
    async with PostgresUnitOfWork(session_factory) as work:
        repos = PostgresRepositorySet.create(work)
        await repos.vendor_operator.save(vendor_operator)
        await work.commit()
    actor = ResolvedActorContext(
        principal_id="verified",
        roles=frozenset({ActorRole.VENDOR_SYSTEM_ADMIN}),
        operator_id=vendor_operator.id,
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
                        "SELECT operator_id, person_id, account_id, resource_id, recorded_at FROM operation_audits"
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
        assert rows[0]["operator_id"] == vendor_operator.id.value
        assert rows[0]["person_id"] is None
        assert rows[0]["account_id"] is None
        assert rows[0]["recorded_at"] == clock.now()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE operation_audits SET operation = '改変'",
        "DELETE FROM operation_audits",
        "DELETE FROM vendor_operators",
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


@pytest.mark.asyncio
async def test_本人未特定の更新は_行を書く前に拒否される(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """素の ActorContext で書き込めた時期は、応答後にロールバックされていた。

    監査の追記が本人を要求する以上、追記できない更新は成立しない。判定を
    確定直前へ置くと、FastAPI の yield 依存が応答後に走るためクライアントは
    成功を受け取る。保存の時点で止め、通常の失敗として扱う。
    """
    actor = ActorContext.vendor_system_admin(principal_id="unresolved")
    root = PostgresCompositionRoot(
        engine, session_factory, FakeClock(datetime(2026, 9, 17, tzinfo=UTC))
    )

    with pytest.raises(UnavailableIdentityError):
        async with root.request_scope(
            authorization=AuthorizationService(actor)
        ) as scope:
            await scope.use_cases.corporate.register.execute(
                RegisterCorporateCommand(
                    name="本人未特定法人",
                    representative_last_name="山田",
                    representative_first_name="太郎",
                )
            )

    async with engine.connect() as connection:
        corporates = (
            await connection.execute(text("SELECT count(*) FROM corporates"))
        ).scalar_one()
        audits = (
            await connection.execute(text("SELECT count(*) FROM operation_audits"))
        ).scalar_one()
    assert corporates == 0
    assert audits == 0
