"""誤って登録された閉局の取消と、その権限。"""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app.application.access_control.models import (
    ActorContext,
    ActorRole,
    ResolvedActorContext,
)
from app.application.access_control.policy import AuthorizationService
from app.application.common.exceptions import AuthorizationError
from app.application.corporate.corporate_access import CorporateAccessService
from app.application.store.management import (
    RevokeStoreClosureCommand,
    RevokeStoreClosureUseCase,
)
from app.domain.foundation.exceptions import DomainError
from app.domain.identity.primitives import AccountPersonId, UserAccountId
from app.domain.store.lifecycle import StoreStatus
from app.domain.store.store import Store
from tests.application.access_helpers import AutoProvisioningCorporateRepository
from tests.factories.store_factory import create_store
from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_organization_management import FakeOrganizationLock
from tests.fakes.in_memory_store_repository import InMemoryStoreRepository
from tests.fakes.null_unit_of_work import NullUnitOfWork

_NOW = datetime(2026, 9, 17, 2, tzinfo=UTC)


def _vendor_actor() -> ResolvedActorContext:
    return ResolvedActorContext(
        principal_id="ベンダー管理者",
        roles=frozenset({ActorRole.VENDOR_SYSTEM_ADMIN}),
        person_id=AccountPersonId.generate(),
        account_id=UserAccountId.generate(),
    )


def _use_case(
    stores: InMemoryStoreRepository, actor: ActorContext
) -> RevokeStoreClosureUseCase:
    return RevokeStoreClosureUseCase(
        stores,
        CorporateAccessService(
            AutoProvisioningCorporateRepository(), AuthorizationService(actor)
        ),
        FakeClock(_NOW),
        NullUnitOfWork(),
        FakeOrganizationLock(),
    )


def _command(store: Store) -> RevokeStoreClosureCommand:
    return RevokeStoreClosureCommand(
        corporate_id=str(store.corporate_id.value),
        store_id=str(store.id.value),
        reason="閉局の操作誤り",
    )


async def _closed_store() -> tuple[InMemoryStoreRepository, Store]:
    store = replace(create_store(), status=StoreStatus.CLOSED)
    stores = InMemoryStoreRepository()
    await stores.save(store)
    return stores, store


@pytest.mark.asyncio
async def test_ベンダー管理者は閉局を取り消して休止へ戻せる() -> None:
    # Arrange
    stores, store = await _closed_store()
    actor = _vendor_actor()

    # Act
    result = await _use_case(stores, actor).execute(_command(store))

    # Assert
    assert result.status == StoreStatus.SUSPENDED
    saved = await stores.get(store.id)
    assert saved is not None and saved.status == StoreStatus.SUSPENDED
    assert saved.status_history[-1].person_id == actor.person_id


@pytest.mark.asyncio
async def test_法人管理者は閉局を取り消せない() -> None:
    """閉局が実質的に往復できる状態遷移にならないようにする。

    判定はユースケースが持つ。ルータ側で先回りして弾くと、経路が増えたときに
    片方だけが緩む。
    """
    # Arrange
    stores, store = await _closed_store()
    actor = ResolvedActorContext(
        principal_id="法人管理者",
        roles=frozenset({ActorRole.CORPORATE_ADMIN}),
        corporate_id=store.corporate_id,
        person_id=AccountPersonId.generate(),
        account_id=UserAccountId.generate(),
    )

    # Act & Assert
    with pytest.raises(AuthorizationError):
        await _use_case(stores, actor).execute(_command(store))
    saved = await stores.get(store.id)
    assert saved is not None and saved.status == StoreStatus.CLOSED


@pytest.mark.asyncio
async def test_本人を特定できない主体は閉局を取り消せない() -> None:
    """履歴には操作者が残るので、本人の分からない取消は成立しない。"""
    # Arrange
    stores, store = await _closed_store()
    actor = ActorContext.vendor_system_admin(principal_id="本人未特定")

    # Act & Assert
    with pytest.raises(AuthorizationError):
        await _use_case(stores, actor).execute(_command(store))


@pytest.mark.asyncio
async def test_閉局していない店舗の取消は拒否される() -> None:
    # Arrange
    store = create_store()
    stores = InMemoryStoreRepository()
    await stores.save(store)

    # Act & Assert
    with pytest.raises(DomainError):
        await _use_case(stores, _vendor_actor()).execute(_command(store))
