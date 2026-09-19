"""店舗状態と管理薬剤師の在任による、新規業務・継続・過去記録の区別。

期待値を実装の式から計算してはならない。以前このテストは判定側と同じ2つの集合を
書き写して期待値を導いており、薬歴の操作がどちらの集合にも入っていないという
抜けを、全ての ``StoreOperation`` を列挙していたにもかかわらず検出できなかった。
ここでは「どの業務がどの区分か」「どの区分が管理薬剤師の在任を要するか」を
テスト側の独立した表として書き、判定の式ではなく**業務の分類そのもの**を固定する。
"""

from dataclasses import replace

import pytest

from app.application.access_control.store_access import (
    MANAGER_REQUIRED_BY_KIND,
    STORE_OPERATION_KINDS,
    StoreOperation,
    StoreOperationKind,
)
from app.application.composition.store_operation_adapter import StoreOperationAdapter
from app.domain.store.lifecycle import StoreStateConflictError, StoreStatus
from app.domain.store.manager_assignment import ManagerAbsenceConflictError
from tests.application.access_helpers import create_vendor_corporate_access
from tests.factories.store_factory import create_manager_assignment, create_store
from tests.fakes.fake_clock import FakeClock
from tests.fakes.in_memory_manager_assignment_repository import (
    InMemoryStoreManagerAssignmentRepository,
)
from tests.fakes.in_memory_store_repository import InMemoryStoreRepository

#: 各業務の区分。実装の表とは独立に書く。
#:
#: 受付・処方箋の登録・調剤の開始・薬歴の作成は、その店舗で新しく始まる業務。
#: 調剤の記録から確定まで、薬歴の確定・訂正は、既に始まった業務の続き。過去の
#: 薬歴の参照だけが店舗状態で止まらない。
_EXPECTED_KINDS: dict[StoreOperation, StoreOperationKind] = {
    StoreOperation.RECORD_RECEPTION: StoreOperationKind.NEW_WORK,
    StoreOperation.REGISTER_PRESCRIPTION: StoreOperationKind.NEW_WORK,
    StoreOperation.START_DISPENSING: StoreOperationKind.NEW_WORK,
    StoreOperation.START_HISTORY: StoreOperationKind.NEW_WORK,
    StoreOperation.RECORD_DISPENSING: StoreOperationKind.CONTINUING,
    StoreOperation.VERIFY_DISPENSING: StoreOperationKind.CONTINUING,
    StoreOperation.COMPLETE_DISPENSING: StoreOperationKind.CONTINUING,
    StoreOperation.FINALIZE_HISTORY: StoreOperationKind.CONTINUING,
    StoreOperation.AMEND_HISTORY: StoreOperationKind.CONTINUING,
    StoreOperation.READ_HISTORY: StoreOperationKind.READ_ONLY,
}

#: 区分と店舗状態から、拒否されるべき組み合わせ。
_FORBIDDEN: dict[StoreOperationKind, frozenset[StoreStatus]] = {
    StoreOperationKind.NEW_WORK: frozenset({StoreStatus.SUSPENDED, StoreStatus.CLOSED}),
    StoreOperationKind.CONTINUING: frozenset({StoreStatus.CLOSED}),
    StoreOperationKind.READ_ONLY: frozenset(),
}

#: 区分ごとに、管理薬剤師の在任を要するか。実装の表とは独立に書く。
#:
#: 薬機法第7条の配置義務は、新しく始める業務を止めることで守る。不在を理由に
#: 継続業務まで止めると、調剤済みの記録や書きかけの薬歴が不在の期間だけ凍結する。
_EXPECTED_MANAGER_REQUIRED: dict[StoreOperationKind, bool] = {
    StoreOperationKind.NEW_WORK: True,
    StoreOperationKind.CONTINUING: False,
    StoreOperationKind.READ_ONLY: False,
}


def test_全ての業務に区分が与えられている() -> None:
    """列挙に足して表へ書き忘れると、その業務だけ無検査で通る。"""
    assert set(STORE_OPERATION_KINDS) == set(StoreOperation)


def test_業務の区分が_業務の性質と一致する() -> None:
    """判定の式ではなく、どの業務が新規業務かという分類そのものを固定する。"""
    assert dict(STORE_OPERATION_KINDS) == _EXPECTED_KINDS


def test_全ての区分に_拒否される状態が定義されている() -> None:
    """区分を増やして拒否条件を決め忘れると、次のテストが空振りする。"""
    assert set(_FORBIDDEN) == set(StoreOperationKind)


def test_全ての区分に_管理薬剤師の要否が定義されている() -> None:
    """区分を増やして要否を書き忘れると、その区分だけ在任を問われない。"""
    assert set(MANAGER_REQUIRED_BY_KIND) == set(StoreOperationKind)


def test_管理薬剤師の要否が_業務の性質と一致する() -> None:
    """店舗状態の区分とは別の軸として、要否そのものを固定する。"""
    assert dict(MANAGER_REQUIRED_BY_KIND) == _EXPECTED_MANAGER_REQUIRED


@pytest.mark.asyncio
@pytest.mark.parametrize("appointed", [True, False], ids=["在任", "不在"])
@pytest.mark.parametrize("status", list(StoreStatus))
@pytest.mark.parametrize("operation", list(StoreOperation))
async def test_店舗状態と管理薬剤師の在任で操作可否が決まる(
    operation: StoreOperation, status: StoreStatus, appointed: bool
) -> None:
    """拒否の理由ごとに違う例外を返す。

    店舗が休止中なのか管理薬剤師が不在なのかで、利用者が次に取る手段が違う。
    同じ符号へ畳むと分岐を書けないので、例外の型まで固定する。店舗状態は
    在任より先に判定する（閉局した店舗に任命は残らないので、先に在任を見ると
    閉局を「不在」として報せることになる）。
    """
    # Arrange
    store = replace(create_store(), status=status)
    stores = InMemoryStoreRepository()
    await stores.save(store)
    managers = InMemoryStoreManagerAssignmentRepository()
    if appointed:
        await managers.save(
            create_manager_assignment(
                corporate_id=store.corporate_id, store_id=store.id
            )
        )
    adapter = StoreOperationAdapter(
        stores, create_vendor_corporate_access(), managers, FakeClock()
    )
    kind = _EXPECTED_KINDS[operation]

    # Act & Assert
    if status in _FORBIDDEN[kind]:
        expected: type[Exception] | None = StoreStateConflictError
    elif _EXPECTED_MANAGER_REQUIRED[kind] and not appointed:
        expected = ManagerAbsenceConflictError
    else:
        expected = None
    if expected is not None:
        with pytest.raises(expected):
            await adapter.require_allowed(
                corporate_id=store.corporate_id, store_id=store.id, operation=operation
            )
    else:
        await adapter.require_allowed(
            corporate_id=store.corporate_id, store_id=store.id, operation=operation
        )

    assert await stores.get(store.id) == store
