"""店舗コード変更ユースケースのテスト。"""

from __future__ import annotations

import pytest

from app.application.store import ChangeStoreCodeCommand, ChangeStoreCodeUseCase
from app.application.store.exceptions import StoreNotFoundError
from app.domain.corporate import CorporateId
from app.domain.store import (
    StoreCodeAlreadyExistsError,
    StoreCodeUniquenessService,
)
from tests.application.access_helpers import create_vendor_corporate_access
from tests.application.store.helpers import save_store
from tests.fakes.in_memory_store_repository import InMemoryStoreRepository


def create_use_case(repository: InMemoryStoreRepository) -> ChangeStoreCodeUseCase:
    return ChangeStoreCodeUseCase(
        repository,
        StoreCodeUniquenessService(repository),
        create_vendor_corporate_access(),
    )


async def test_change_store_code_sets_code() -> None:
    # Arrange
    repository = InMemoryStoreRepository()
    corporate_id = CorporateId.generate()
    store = await save_store(repository, corporate_id=corporate_id)
    use_case = create_use_case(repository)

    # Act
    await use_case.execute(
        ChangeStoreCodeCommand(
            corporate_id=str(corporate_id.value),
            store_id=str(store.id.value),
            new_code="ST-001",
        )
    )

    # Assert
    actual = await repository.get(store.id)
    assert actual is not None
    assert actual.code is not None
    assert actual.code.value == "ST-001"


@pytest.mark.parametrize("cleared", [None, "", "   "])
async def test_change_store_code_clears_code(cleared: str | None) -> None:
    # Arrange: None・空文字・空白のみは、いずれも「解除」として同じ結果になる
    repository = InMemoryStoreRepository()
    corporate_id = CorporateId.generate()
    store = await save_store(repository, corporate_id=corporate_id, code="ST-001")
    use_case = create_use_case(repository)

    # Act
    await use_case.execute(
        ChangeStoreCodeCommand(
            corporate_id=str(corporate_id.value),
            store_id=str(store.id.value),
            new_code=cleared,
        )
    )

    # Assert
    actual = await repository.get(store.id)
    assert actual is not None
    assert actual.code is None


async def test_change_store_code_keeps_own_code_without_duplicate_error() -> None:
    # Arrange: 同じコードを再送しても自分自身との重複で失敗してはならない
    repository = InMemoryStoreRepository()
    corporate_id = CorporateId.generate()
    store = await save_store(repository, corporate_id=corporate_id, code="ST-001")
    use_case = create_use_case(repository)

    # Act
    await use_case.execute(
        ChangeStoreCodeCommand(
            corporate_id=str(corporate_id.value),
            store_id=str(store.id.value),
            new_code="ST-001",
        )
    )

    # Assert
    actual = await repository.get(store.id)
    assert actual is not None
    assert actual.code is not None
    assert actual.code.value == "ST-001"


async def test_change_store_code_rejects_code_used_by_another_store() -> None:
    # Arrange
    repository = InMemoryStoreRepository()
    corporate_id = CorporateId.generate()
    target = await save_store(
        repository, corporate_id=corporate_id, name="サンプル薬局"
    )
    await save_store(
        repository, corporate_id=corporate_id, name="別の薬局", code="ST-001"
    )
    use_case = create_use_case(repository)

    # Act
    with pytest.raises(StoreCodeAlreadyExistsError):
        await use_case.execute(
            ChangeStoreCodeCommand(
                corporate_id=str(corporate_id.value),
                store_id=str(target.id.value),
                new_code="ST-001",
            )
        )

    # Assert
    actual = await repository.get(target.id)
    assert actual is not None
    assert actual.code is None


async def test_change_store_code_rejects_store_of_another_corporate() -> None:
    # Arrange
    repository = InMemoryStoreRepository()
    store = await save_store(repository, corporate_id=CorporateId.generate())
    use_case = create_use_case(repository)

    # Act / Assert
    with pytest.raises(StoreNotFoundError):
        await use_case.execute(
            ChangeStoreCodeCommand(
                corporate_id=str(CorporateId.generate().value),
                store_id=str(store.id.value),
                new_code="ST-001",
            )
        )
