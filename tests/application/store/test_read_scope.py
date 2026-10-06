"""永続化実装に依存せず店舗の閲覧範囲を守る。"""

import pytest

from app.application.access_control.models import ActorRole, ResolvedActorContext
from app.application.access_control.policy import AuthorizationService
from app.application.corporate.corporate_access import CorporateAccessService
from app.application.store.exceptions import StoreNotFoundError
from app.application.store.get_store import GetStoreQuery, GetStoreUseCase
from app.application.store.list_stores import ListStoresQuery, ListStoresUseCase
from app.domain.identity.primitives import AccountPersonId, UserAccountId
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
    actor = ResolvedActorContext(
        principal_id="確認済み",
        roles=frozenset({role}),
        corporate_id=allowed.corporate_id,
        person_id=AccountPersonId.generate(),
        account_id=UserAccountId.generate(),
        store_ids=frozenset() if empty_scope else frozenset({allowed.id}),
    )
    access = CorporateAccessService(
        AutoProvisioningCorporateRepository(), AuthorizationService(actor)
    )
    details = GetStoreUseCase(repository, access)
    unrestricted = role in {ActorRole.VENDOR_SYSTEM_ADMIN, ActorRole.CORPORATE_ADMIN}

    # Act
    rows = await ListStoresUseCase(repository, access).execute(
        ListStoresQuery(corporate_id=str(allowed.corporate_id.value))
    )

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
