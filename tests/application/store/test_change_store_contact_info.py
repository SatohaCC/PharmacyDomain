"""店舗連絡先変更ユースケースのテスト。"""

from __future__ import annotations

import pytest

from app.application.store import (
    ChangeStoreContactInfoCommand,
    ChangeStoreContactInfoUseCase,
)
from app.base.domain.exceptions import DomainValidationError
from app.domain.corporate import CorporateId
from tests.application.access_helpers import create_vendor_corporate_access
from tests.application.store.helpers import save_store
from tests.fakes.in_memory_store_repository import InMemoryStoreRepository


async def test_change_store_contact_info_updates_all_fields() -> None:
    # Arrange
    repository = InMemoryStoreRepository()
    corporate_id = CorporateId.generate()
    store = await save_store(repository, corporate_id=corporate_id)
    use_case = ChangeStoreContactInfoUseCase(
        repository, create_vendor_corporate_access()
    )

    # Act
    await use_case.execute(
        ChangeStoreContactInfoCommand(
            corporate_id=str(corporate_id.value),
            store_id=str(store.id.value),
            phone_number="06-1234-5678",
            fax_number="06-1234-5679",
            email="Store@Example.COM",
        )
    )

    # Assert
    actual = await repository.get(store.id)
    assert actual is not None
    assert actual.contact_info.phone_number.value == "0612345678"
    assert actual.contact_info.fax_number is not None
    assert actual.contact_info.fax_number.value == "0612345679"
    assert actual.contact_info.email is not None
    assert actual.contact_info.email.value == "store@example.com"


@pytest.mark.parametrize("blank", [None, "", "   "])
async def test_change_store_contact_info_clears_optional_fields(
    blank: str | None,
) -> None:
    # Arrange: 任意項目は None・空文字・空白のみのいずれでも解除として扱う
    repository = InMemoryStoreRepository()
    corporate_id = CorporateId.generate()
    store = await save_store(repository, corporate_id=corporate_id)
    use_case = ChangeStoreContactInfoUseCase(
        repository, create_vendor_corporate_access()
    )
    await use_case.execute(
        ChangeStoreContactInfoCommand(
            corporate_id=str(corporate_id.value),
            store_id=str(store.id.value),
            phone_number="0312345678",
            fax_number="0312345679",
            email="store@example.com",
        )
    )

    # Act
    await use_case.execute(
        ChangeStoreContactInfoCommand(
            corporate_id=str(corporate_id.value),
            store_id=str(store.id.value),
            phone_number="0312345678",
            fax_number=blank,
            email=blank,
        )
    )

    # Assert
    actual = await repository.get(store.id)
    assert actual is not None
    assert actual.contact_info.fax_number is None
    assert actual.contact_info.email is None


async def test_change_store_contact_info_rejects_blank_phone_number() -> None:
    # Arrange: 電話番号は必須項目
    repository = InMemoryStoreRepository()
    corporate_id = CorporateId.generate()
    store = await save_store(repository, corporate_id=corporate_id)
    use_case = ChangeStoreContactInfoUseCase(
        repository, create_vendor_corporate_access()
    )

    # Act
    with pytest.raises(DomainValidationError):
        await use_case.execute(
            ChangeStoreContactInfoCommand(
                corporate_id=str(corporate_id.value),
                store_id=str(store.id.value),
                phone_number="",
            )
        )

    # Assert
    actual = await repository.get(store.id)
    assert actual is not None
    assert actual.contact_info.phone_number.value == "0312345678"
