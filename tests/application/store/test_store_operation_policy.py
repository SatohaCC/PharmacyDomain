"""店舗状態による新規業務・継続・過去記録の区別。

期待値を実装の式から計算してはならない。以前このテストは判定側と同じ2つの集合を
書き写して期待値を導いており、薬歴の操作がどちらの集合にも入っていないという
抜けを、全ての ``StoreOperation`` を列挙していたにもかかわらず検出できなかった。
ここでは「どの業務がどの区分か」をテスト側の独立した表として書き、判定の式では
なく**業務の分類そのもの**を固定する。
"""

from dataclasses import replace

import pytest

from app.application.access_control.store_access import (
    STORE_OPERATION_KINDS,
    StoreOperation,
    StoreOperationKind,
)
from app.application.composition.store_operation_adapter import StoreOperationAdapter
from app.domain.foundation.exceptions import DomainError
from app.domain.store.lifecycle import StoreStatus
from tests.application.access_helpers import create_vendor_corporate_access
from tests.factories.store_factory import create_store
from tests.fakes.in_memory_store_repository import InMemoryStoreRepository

#: 各業務の区分。実装の表とは独立に書く。
#:
#: 受付・処方箋の登録・調剤の開始・薬歴の作成は、その店舗で新しく始まる業務。
#: 調剤の記録から確定まで、所属と管理薬剤師の整理、薬歴の確定・訂正は、既に
#: 始まった業務の続き。過去の薬歴の参照だけが店舗状態で止まらない。
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
    StoreOperation.ASSIGN_STAFF: StoreOperationKind.CONTINUING,
    StoreOperation.ASSIGN_MANAGER: StoreOperationKind.CONTINUING,
    StoreOperation.READ_HISTORY: StoreOperationKind.READ_ONLY,
}

#: 区分と店舗状態から、拒否されるべき組み合わせ。
_FORBIDDEN: dict[StoreOperationKind, frozenset[StoreStatus]] = {
    StoreOperationKind.NEW_WORK: frozenset({StoreStatus.SUSPENDED, StoreStatus.CLOSED}),
    StoreOperationKind.CONTINUING: frozenset({StoreStatus.CLOSED}),
    StoreOperationKind.READ_ONLY: frozenset(),
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


@pytest.mark.asyncio
@pytest.mark.parametrize("status", list(StoreStatus))
@pytest.mark.parametrize("operation", list(StoreOperation))
async def test_店舗状態ごとの操作可否が業務区分に一致する(
    status: StoreStatus, operation: StoreOperation
) -> None:
    # Arrange
    store = replace(create_store(), status=status)
    repository = InMemoryStoreRepository()
    await repository.save(store)
    adapter = StoreOperationAdapter(repository, create_vendor_corporate_access())
    forbidden = status in _FORBIDDEN[_EXPECTED_KINDS[operation]]

    # Act & Assert
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
