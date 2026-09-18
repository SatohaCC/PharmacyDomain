"""実際の保存対象で新規業務と継続業務を区別する。"""

from dataclasses import replace

import pytest

from app.application.access_control import ActorContext, AuthorizationService
from app.application.composition.clinical_store_guard import ClinicalStoreWriteGuard
from app.application.composition.store_operation_adapter import StoreOperationAdapter
from app.domain.foundation.exceptions import DomainError
from app.domain.store.lifecycle import StoreStatus
from tests.application.access_helpers import create_vendor_corporate_access
from tests.factories.dispensing_factory import create_dispensing
from tests.factories.prescription_factory import create_prescription
from tests.factories.store_factory import create_store
from tests.fakes.fake_organization_management import FakeOrganizationLock
from tests.fakes.in_memory_store_repository import InMemoryStoreRepository


@pytest.mark.asyncio
@pytest.mark.parametrize("state", list(StoreStatus))
@pytest.mark.parametrize(
    "kind,is_new", [("prescription", True), ("dispensing", True), ("dispensing", False)]
)
async def test_保存対象店舗の状態で業務の開始と継続を区別する(
    state: StoreStatus, kind: str, is_new: bool
) -> None:
    store = replace(create_store(), status=state)
    stores = InMemoryStoreRepository()
    await stores.save(store)
    entity = (
        create_prescription(corporate_id=store.corporate_id)
        if kind == "prescription"
        else create_dispensing(corporate_id=store.corporate_id)
    )
    entity = replace(entity, store_id=store.id)
    guard = ClinicalStoreWriteGuard(
        StoreOperationAdapter(stores, create_vendor_corporate_access()),
        AuthorizationService(ActorContext.vendor_system_admin(principal_id="テスト")),
        FakeOrganizationLock(),
    )
    denied = state == StoreStatus.CLOSED or (is_new and state == StoreStatus.SUSPENDED)
    if denied:
        with pytest.raises(DomainError):
            await guard.check(entity, is_new)
    else:
        await guard.check(entity, is_new)
