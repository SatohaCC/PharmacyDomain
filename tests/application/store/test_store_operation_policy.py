"""店舗状態による新規業務・継続・過去記録の区別。"""

from dataclasses import replace

import pytest

from app.application.access_control.store_access import StoreOperation
from app.application.composition.store_operation_adapter import StoreOperationAdapter
from app.domain.foundation.exceptions import DomainError
from app.domain.store.lifecycle import StoreStatus
from tests.application.access_helpers import create_vendor_corporate_access
from tests.factories.store_factory import create_store
from tests.fakes.in_memory_store_repository import InMemoryStoreRepository


@pytest.mark.asyncio
@pytest.mark.parametrize("status", list(StoreStatus))
@pytest.mark.parametrize("operation", list(StoreOperation))
async def test_店舗状態ごとの操作可否が業務区分に一致する(
    status: StoreStatus, operation: StoreOperation
) -> None:
    store = replace(create_store(), status=status)
    repository = InMemoryStoreRepository()
    await repository.save(store)
    adapter = StoreOperationAdapter(repository, create_vendor_corporate_access())
    new_work = {
        StoreOperation.RECORD_RECEPTION,
        StoreOperation.REGISTER_PRESCRIPTION,
        StoreOperation.START_DISPENSING,
    }
    continuation = {
        StoreOperation.RECORD_DISPENSING,
        StoreOperation.VERIFY_DISPENSING,
        StoreOperation.COMPLETE_DISPENSING,
        StoreOperation.ASSIGN_STAFF,
        StoreOperation.ASSIGN_MANAGER,
    }
    forbidden = (operation in new_work and status != StoreStatus.ACTIVE) or (
        operation in continuation and status == StoreStatus.CLOSED
    )

    if forbidden:
        with pytest.raises(DomainError):
            await adapter.require_allowed(
                corporate_id=store.corporate_id, store_id=store.id, operation=operation
            )
    else:
        await adapter.require_allowed(
            corporate_id=store.corporate_id, store_id=store.id, operation=operation
        )

    assert await repository.get(store.id) == store
