"""本番配線の店舗範囲が取得と一覧の両方へ適用される。"""

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.application.access_control.models import ActorRole, ResolvedActorContext
from app.application.access_control.policy import AuthorizationService
from app.application.store.exceptions import StoreNotFoundError
from app.application.store.get_store import GetStoreQuery
from app.application.store.list_stores import ListStoresQuery
from app.domain.identity.primitives import AccountPersonId, UserAccountId
from app.infrastructure.di.root import PostgresCompositionRoot
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.infrastructure.postgres.repositories.repository_set import (
    PostgresRepositorySet,
)
from tests.factories.store_factory import create_store
from tests.fakes.fake_clock import FakeClock
from tests.infrastructure.postgres.helpers import create_corporate


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [ActorRole.STORE_OPERATOR, ActorRole.STORE_VIEWER])
async def test_店舗ロールの一覧と詳細は許可店舗だけを返す(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    role: ActorRole,
) -> None:
    corporate = create_corporate()
    allowed = create_store(corporate_id=corporate.id)
    hidden = create_store(corporate_id=corporate.id, name="非公開店舗")
    async with PostgresUnitOfWork(session_factory) as work:
        repos = PostgresRepositorySet.create(work)
        await repos.corporate.save(corporate)
        await repos.store.save(allowed)
        await repos.store.save(hidden)
        await work.commit()
    actor = ResolvedActorContext(
        principal_id="確認済み",
        roles=frozenset({role}),
        person_id=AccountPersonId.generate(),
        account_id=UserAccountId.generate(),
        corporate_id=corporate.id,
        store_ids=frozenset({allowed.id}),
    )
    root = PostgresCompositionRoot(
        engine, session_factory, FakeClock(datetime(2026, 9, 17, tzinfo=UTC))
    )
    async with root.request_scope(authorization=AuthorizationService(actor)) as scope:
        result = await scope.use_cases.store.list_by_corporate.execute(
            ListStoresQuery(corporate_id=str(corporate.id.value))
        )
        assert [item.id for item in result] == [str(allowed.id.value)]
        detail = await scope.use_cases.store.get.execute(
            GetStoreQuery(
                corporate_id=str(corporate.id.value), store_id=str(allowed.id.value)
            )
        )
        assert detail.id == str(allowed.id.value)
        with pytest.raises(StoreNotFoundError):
            await scope.use_cases.store.get.execute(
                GetStoreQuery(
                    corporate_id=str(corporate.id.value), store_id=str(hidden.id.value)
                )
            )
