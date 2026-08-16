"""店舗住所変更ユースケースのテスト。"""

from __future__ import annotations

import pytest

from app.application.store import ChangeStoreAddressCommand, ChangeStoreAddressUseCase
from app.application.store.exceptions import StoreNotFoundError
from app.base.domain.exceptions import DomainValidationError
from app.domain.corporate import CorporateId
from tests.application.access_helpers import create_vendor_corporate_access
from tests.application.store.helpers import save_store
from tests.fakes.in_memory_store_repository import InMemoryStoreRepository


async def test_change_store_address_updates_and_persists_store() -> None:
    # Arrange
    repository = InMemoryStoreRepository()
    corporate_id = CorporateId.generate()
    store = await save_store(repository, corporate_id=corporate_id)
    use_case = ChangeStoreAddressUseCase(repository, create_vendor_corporate_access())

    # Act
    await use_case.execute(
        ChangeStoreAddressCommand(
            corporate_id=str(corporate_id.value),
            store_id=str(store.id.value),
            postal_code="5300001",
            address="大阪府大阪市北区梅田1-1-1",
        )
    )

    # Assert
    actual = await repository.get(store.id)
    assert actual is not None
    assert actual.address.postal_code.value == "530-0001"
    assert actual.address.address.value == "大阪府大阪市北区梅田1-1-1"


async def test_change_store_address_rejects_invalid_postal_code() -> None:
    # Arrange
    repository = InMemoryStoreRepository()
    corporate_id = CorporateId.generate()
    store = await save_store(repository, corporate_id=corporate_id)
    use_case = ChangeStoreAddressUseCase(repository, create_vendor_corporate_access())

    # Act
    with pytest.raises(DomainValidationError):
        await use_case.execute(
            ChangeStoreAddressCommand(
                corporate_id=str(corporate_id.value),
                store_id=str(store.id.value),
                postal_code="12345",
                address="大阪府大阪市北区梅田1-1-1",
            )
        )

    # Assert: 変更前の住所が保持されていること
    actual = await repository.get(store.id)
    assert actual is not None
    assert actual.address.address.value == "東京都千代田区1-2-3"


async def test_change_store_address_rejects_store_of_another_corporate() -> None:
    # Arrange
    repository = InMemoryStoreRepository()
    store = await save_store(repository, corporate_id=CorporateId.generate())
    use_case = ChangeStoreAddressUseCase(repository, create_vendor_corporate_access())

    # Act / Assert
    with pytest.raises(StoreNotFoundError):
        await use_case.execute(
            ChangeStoreAddressCommand(
                corporate_id=str(CorporateId.generate().value),
                store_id=str(store.id.value),
                postal_code="5300001",
                address="大阪府大阪市北区梅田1-1-1",
            )
        )
