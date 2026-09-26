"""実際の保存対象で新規業務と継続業務を区別する。

「どの集約のどの保存がどの業務に当たるか」と「その業務が店舗状態で止まるか」は
別の判断である。後者は ``test_store_operation_policy`` が業務区分の表として
固定するので、ここでは前者――保存対象から業務への写像――を対象にする。
薬歴の写像だけが検査されていなかった時期に、閉局した店舗で新規の薬歴を
作成できる状態が残っていた。
"""

from dataclasses import replace

import pytest

from app.application.access_control.models import ActorContext
from app.application.access_control.policy import AuthorizationService
from app.application.access_control.store_access import (
    StoreOperation,
    StoreOperationBoundary,
)
from app.application.composition.clinical_store_guard import ClinicalStoreWriteGuard
from app.application.composition.store_operation_adapter import StoreOperationAdapter
from app.domain.corporate.primitives import CorporateId
from app.domain.foundation.exceptions import DomainError
from app.domain.store.lifecycle import StoreStateConflictError, StoreStatus
from app.domain.store.manager_assignment import ManagerAbsenceConflictError
from app.domain.store.primitives import StoreId
from tests.application.access_helpers import create_vendor_corporate_access
from tests.factories.dispensing_factory import create_dispensing
from tests.factories.medication_history_factory import (
    create_independent_follow_up_record,
    create_record,
    finalize_record_with_review,
)
from tests.factories.prescription_factory import create_prescription
from tests.factories.store_factory import create_manager_assignment, create_store
from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_organization_management import FakeOrganizationLock
from tests.fakes.in_memory_manager_assignment_repository import (
    InMemoryStoreManagerAssignmentRepository,
)
from tests.fakes.in_memory_store_repository import InMemoryStoreRepository


class RecordingStoreOperationBoundary(StoreOperationBoundary):
    """問い合わせられた業務を記録するだけの境界。"""

    def __init__(self) -> None:
        self.operations: list[StoreOperation] = []

    async def require_allowed(
        self, *, corporate_id: CorporateId, store_id: StoreId, operation: StoreOperation
    ) -> None:
        """判定せず、問い合わせ内容だけを残す。"""
        self.operations.append(operation)


def _authorization() -> AuthorizationService:
    return AuthorizationService(ActorContext.vendor_system_admin(principal_id="テスト"))


def _aggregate(kind: str, *, corporate_id: CorporateId, store_id: StoreId) -> object:
    if kind == "prescription":
        entity: object = create_prescription(corporate_id=corporate_id)
    elif kind == "dispensing":
        entity = create_dispensing(corporate_id=corporate_id)
    elif kind == "follow_up":
        source = finalize_record_with_review(
            create_record(corporate_id=corporate_id, store_id=store_id)
        )
        return create_independent_follow_up_record(source, store_id=store_id)
    else:
        entity = create_record(corporate_id=corporate_id)
    return replace(entity, store_id=store_id)  # type: ignore[type-var]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kind", "is_new", "expected"),
    [
        ("prescription", True, StoreOperation.REGISTER_PRESCRIPTION),
        ("prescription", False, StoreOperation.RECORD_DISPENSING),
        ("dispensing", True, StoreOperation.START_DISPENSING),
        ("dispensing", False, StoreOperation.RECORD_DISPENSING),
        # 新規の薬歴は、その店舗で新しく始まる業務として問い合わせる。
        ("history", True, StoreOperation.START_HISTORY),
        ("history", False, StoreOperation.AMEND_HISTORY),
        ("follow_up", True, StoreOperation.START_HISTORY),
        ("follow_up", False, StoreOperation.AMEND_HISTORY),
    ],
)
async def test_保存対象から業務への写像を固定する(
    kind: str, is_new: bool, expected: StoreOperation
) -> None:
    # Arrange
    store = create_store()
    boundary = RecordingStoreOperationBoundary()
    guard = ClinicalStoreWriteGuard(boundary, _authorization(), FakeOrganizationLock())
    entity = _aggregate(kind, corporate_id=store.corporate_id, store_id=store.id)

    # Act
    await guard.check(entity, is_new)

    # Assert
    assert boundary.operations == [expected]


@pytest.mark.asyncio
@pytest.mark.parametrize("state", list(StoreStatus))
@pytest.mark.parametrize(
    ("kind", "is_new"),
    [
        ("prescription", True),
        ("dispensing", True),
        ("dispensing", False),
        ("history", True),
        ("history", False),
        ("follow_up", True),
    ],
)
async def test_保存対象店舗の状態で業務の開始と継続を区別する(
    state: StoreStatus, kind: str, is_new: bool
) -> None:
    # Arrange
    store = replace(create_store(), status=state)
    stores = InMemoryStoreRepository()
    await stores.save(store)
    # 管理薬剤師の在任は別の軸なので、ここでは在任させたうえで店舗状態だけを
    # 動かす。不在のときの拒否は ``test_store_operation_policy`` が固定する。
    managers = InMemoryStoreManagerAssignmentRepository()
    await managers.save(
        create_manager_assignment(corporate_id=store.corporate_id, store_id=store.id)
    )
    guard = ClinicalStoreWriteGuard(
        StoreOperationAdapter(
            stores, create_vendor_corporate_access(), managers, FakeClock()
        ),
        _authorization(),
        FakeOrganizationLock(),
    )
    entity = _aggregate(kind, corporate_id=store.corporate_id, store_id=store.id)
    denied = state == StoreStatus.CLOSED or (is_new and state == StoreStatus.SUSPENDED)

    # Act & Assert
    if denied:
        with pytest.raises(DomainError):
            await guard.check(entity, is_new)
    else:
        await guard.check(entity, is_new)


@pytest.mark.asyncio
async def test_休止店舗ではフォローアップの新規薬歴作成を拒否する() -> None:
    """TC-17: FOLLOW_UP 下書きも新規業務として休止店舗で拒否する。"""
    store = replace(create_store(), status=StoreStatus.SUSPENDED)
    stores = InMemoryStoreRepository()
    await stores.save(store)
    managers = InMemoryStoreManagerAssignmentRepository()
    await managers.save(
        create_manager_assignment(corporate_id=store.corporate_id, store_id=store.id)
    )
    guard = ClinicalStoreWriteGuard(
        StoreOperationAdapter(
            stores, create_vendor_corporate_access(), managers, FakeClock()
        ),
        _authorization(),
        FakeOrganizationLock(),
    )
    follow_up = _aggregate(
        "follow_up", corporate_id=store.corporate_id, store_id=store.id
    )

    with pytest.raises(StoreStateConflictError):
        await guard.check(follow_up, is_new=True)


@pytest.mark.asyncio
async def test_管理薬剤師不在の店舗ではフォローアップ起票を拒否する() -> None:
    """TC-18: 有効店舗でも管理薬剤師の在任が無ければ起票を拒否する。"""
    store = create_store()
    stores = InMemoryStoreRepository()
    await stores.save(store)
    managers = InMemoryStoreManagerAssignmentRepository()
    guard = ClinicalStoreWriteGuard(
        StoreOperationAdapter(
            stores, create_vendor_corporate_access(), managers, FakeClock()
        ),
        _authorization(),
        FakeOrganizationLock(),
    )
    follow_up = _aggregate(
        "follow_up", corporate_id=store.corporate_id, store_id=store.id
    )

    with pytest.raises(ManagerAbsenceConflictError):
        await guard.check(follow_up, is_new=True)
