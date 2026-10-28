"""永続化実装に依存せず店舗の閲覧範囲を守る。"""

import pytest

from app.application.access_control.boundary_models import (
    ActorRole,
    ResolvedActorContext,
)
from app.application.access_control.policies import AuthorizationService
from app.application.corporate.commands.services.corporate_access import (
    CorporateAccessService,
)
from app.application.store.errors import StoreNotFoundError
from app.application.store.queries.get_store import GetStoreUseCase
from app.application.store.queries.list_stores import ListStoresUseCase
from app.application.store.queries.models import GetStoreQuery, ListStoresQuery
from app.domain.shared.actor import AccountPersonId, UserAccountId
from app.infrastructure.readers.store_get_store import GetStoreProjection
from app.infrastructure.readers.store_list_stores import ListStoresProjection
from tests.application.access_helpers import AutoProvisioningCorporateRepository
from tests.factories.store_factory import create_store
from tests.fakes.in_memory_store_repository import InMemoryStoreRepository


@pytest.mark.parametrize("role", list(ActorRole))
@pytest.mark.parametrize("empty_scope", [False, True])
async def test_店舗参照_操作主体の範囲に応じて詳細と一覧を制限する(
    role: ActorRole, empty_scope: bool
) -> None:
    # Arrange
    allowed = create_store()
    hidden = create_store(corporate_id=allowed.corporate_id, name="非公開店舗")
    repository = InMemoryStoreRepository()
    await repository.save(allowed)
    await repository.save(hidden)
    if role == ActorRole.STORE_MANAGER and empty_scope:
        with pytest.raises(ValueError):
            ResolvedActorContext(
                principal_id="テスト管理薬剤師",
                roles=frozenset({role}),
                corporate_id=allowed.corporate_id,
                person_id=AccountPersonId.generate(),
                account_id=UserAccountId.generate(),
            )
        return
    actor = ResolvedActorContext(
        principal_id="確認済み",
        roles=frozenset({role}),
        corporate_id=allowed.corporate_id,
        person_id=AccountPersonId.generate(),
        account_id=UserAccountId.generate(),
        store_ids=frozenset() if empty_scope else frozenset({allowed.id}),
        managed_store_ids=frozenset({allowed.id})
        if role == ActorRole.STORE_MANAGER
        else frozenset(),
    )
    access = CorporateAccessService(
        AutoProvisioningCorporateRepository(), AuthorizationService(actor)
    )
    details = GetStoreUseCase(
        reader=GetStoreProjection(repository), corporate_access=access
    )
    unrestricted = role in {ActorRole.VENDOR_SYSTEM_ADMIN, ActorRole.CORPORATE_ADMIN}

    # Act
    rows = await ListStoresUseCase(
        reader=ListStoresProjection(repository), corporate_access=access
    ).execute(ListStoresQuery(corporate_id=str(allowed.corporate_id.value)))

    # Assert
    expected = {allowed.id, hidden.id} if unrestricted else actor.store_ids
    assert {row.id for row in rows} == {str(store_id.value) for store_id in expected}
    for store in (allowed, hidden):
        query = GetStoreQuery(
            corporate_id=str(store.corporate_id.value), store_id=str(store.id.value)
        )
        if store.id in expected:
            assert (await details.execute(query)).id == str(store.id.value)
        else:
            with pytest.raises(StoreNotFoundError):
                await details.execute(query)
