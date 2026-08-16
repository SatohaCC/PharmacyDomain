"""店舗ドメインサービス（一意性検証）のテスト。"""

from __future__ import annotations

import pytest

from app.domain.corporate import CorporateId
from app.domain.store import (
    StoreCode,
    StoreCodeAlreadyExistsError,
    StoreCodeUniquenessService,
    StoreName,
    StoreNameAlreadyExistsError,
    StoreNameUniquenessService,
)
from tests.factories.store_factory import create_store
from tests.fakes.in_memory_store_repository import InMemoryStoreRepository


async def test_ensure_name_is_unique_passes_when_name_does_not_exist() -> None:
    # Arrange
    repository = InMemoryStoreRepository()
    service = StoreNameUniquenessService(repository)

    # Act / Assert: 例外が出ないこと自体が期待結果
    await service.ensure_name_is_unique(
        corporate_id=CorporateId.generate(),
        name=StoreName("サンプル薬局"),
    )


async def test_ensure_name_is_unique_raises_when_same_corporate_has_the_name() -> None:
    # Arrange
    repository = InMemoryStoreRepository()
    corporate_id = CorporateId.generate()
    await repository.save(create_store(corporate_id=corporate_id, name="サンプル薬局"))
    service = StoreNameUniquenessService(repository)

    # Act
    with pytest.raises(StoreNameAlreadyExistsError) as exc_info:
        await service.ensure_name_is_unique(
            corporate_id=corporate_id,
            name=StoreName("サンプル薬局"),
        )

    # Assert
    assert "サンプル薬局" in str(exc_info.value)


async def test_ensure_name_is_unique_allows_same_name_in_another_corporate() -> None:
    # Arrange: 店舗名の一意性は法人単位。別法人の同名は許可される
    repository = InMemoryStoreRepository()
    await repository.save(
        create_store(corporate_id=CorporateId.generate(), name="サンプル薬局")
    )
    service = StoreNameUniquenessService(repository)

    # Act / Assert
    await service.ensure_name_is_unique(
        corporate_id=CorporateId.generate(),
        name=StoreName("サンプル薬局"),
    )


async def test_ensure_name_is_unique_excludes_the_store_itself() -> None:
    # Arrange
    repository = InMemoryStoreRepository()
    corporate_id = CorporateId.generate()
    store = create_store(corporate_id=corporate_id, name="サンプル薬局")
    await repository.save(store)
    service = StoreNameUniquenessService(repository)

    # Act / Assert: 自分自身の名称は重複とみなさない
    await service.ensure_name_is_unique(
        corporate_id=corporate_id,
        name=StoreName("サンプル薬局"),
        excluding_id=store.id,
    )


async def test_ensure_code_is_unique_raises_when_same_corporate_has_the_code() -> None:
    # Arrange
    repository = InMemoryStoreRepository()
    corporate_id = CorporateId.generate()
    await repository.save(
        create_store(corporate_id=corporate_id, name="サンプル薬局", code="ST-001")
    )
    service = StoreCodeUniquenessService(repository)

    # Act
    with pytest.raises(StoreCodeAlreadyExistsError) as exc_info:
        await service.ensure_code_is_unique(
            corporate_id=corporate_id,
            code=StoreCode("ST-001"),
        )

    # Assert
    assert "ST-001" in str(exc_info.value)


async def test_ensure_code_is_unique_allows_same_code_in_another_corporate() -> None:
    # Arrange
    repository = InMemoryStoreRepository()
    await repository.save(
        create_store(
            corporate_id=CorporateId.generate(), name="サンプル薬局", code="ST-001"
        )
    )
    service = StoreCodeUniquenessService(repository)

    # Act / Assert
    await service.ensure_code_is_unique(
        corporate_id=CorporateId.generate(),
        code=StoreCode("ST-001"),
    )


async def test_ensure_code_is_unique_excludes_the_store_itself() -> None:
    # Arrange
    repository = InMemoryStoreRepository()
    corporate_id = CorporateId.generate()
    store = create_store(corporate_id=corporate_id, name="サンプル薬局", code="ST-001")
    await repository.save(store)
    service = StoreCodeUniquenessService(repository)

    # Act / Assert
    await service.ensure_code_is_unique(
        corporate_id=corporate_id,
        code=StoreCode("ST-001"),
        excluding_id=store.id,
    )
