"""店舗詳細取得ユースケースのテスト。"""

from __future__ import annotations

import pytest

from app.application.store import GetStoreQuery, GetStoreUseCase, StoreDto
from app.application.store.exceptions import StoreNotFoundError
from app.domain.corporate import CorporateId
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.store import StoreId
from tests.application.access_helpers import create_vendor_corporate_access
from tests.application.store.helpers import save_store
from tests.factories.store_factory import VALID_INSURANCE_NUMBER
from tests.fakes.in_memory_store_repository import InMemoryStoreRepository


async def test_get_store_returns_dto() -> None:
    # Arrange
    repository = InMemoryStoreRepository()
    corporate_id = CorporateId.generate()
    store = await save_store(
        repository,
        corporate_id=corporate_id,
        code="ST-001",
        insurance_pharmacy_number=VALID_INSURANCE_NUMBER,
    )
    use_case = GetStoreUseCase(repository, create_vendor_corporate_access())

    # Act
    actual = await use_case.execute(
        GetStoreQuery(
            corporate_id=str(corporate_id.value),
            store_id=str(store.id.value),
        )
    )

    # Assert
    assert actual == StoreDto(
        id=str(store.id.value),
        corporate_id=str(corporate_id.value),
        name="サンプル薬局",
        name_kana="サンプルヤッキョク",
        name_romaji=None,
        postal_code="123-4567",
        address="東京都千代田区1-2-3",
        phone_number="0312345678",
        fax_number=None,
        email=None,
        code="ST-001",
        insurance_pharmacy_number=VALID_INSURANCE_NUMBER,
    )


async def test_get_store_hides_store_of_another_corporate() -> None:
    # Arrange: 他法人の店舗は「存在しない」と同じ扱いにし、存在の推測を許さない
    repository = InMemoryStoreRepository()
    store = await save_store(repository, corporate_id=CorporateId.generate())
    use_case = GetStoreUseCase(repository, create_vendor_corporate_access())

    # Act / Assert
    with pytest.raises(StoreNotFoundError):
        await use_case.execute(
            GetStoreQuery(
                corporate_id=str(CorporateId.generate().value),
                store_id=str(store.id.value),
            )
        )


async def test_get_store_raises_when_store_does_not_exist() -> None:
    # Arrange
    repository = InMemoryStoreRepository()
    use_case = GetStoreUseCase(repository, create_vendor_corporate_access())

    # Act / Assert
    with pytest.raises(StoreNotFoundError):
        await use_case.execute(
            GetStoreQuery(
                corporate_id=str(CorporateId.generate().value),
                store_id=str(StoreId.generate().value),
            )
        )


async def test_get_store_raises_validation_error_for_malformed_id() -> None:
    # Arrange: 未検出（404相当）と入力値エラー（400相当）が区別されること
    repository = InMemoryStoreRepository()
    use_case = GetStoreUseCase(repository, create_vendor_corporate_access())

    # Act / Assert
    with pytest.raises(DomainValidationError):
        await use_case.execute(
            GetStoreQuery(
                corporate_id=str(CorporateId.generate().value),
                store_id="not-a-uuid",
            )
        )
