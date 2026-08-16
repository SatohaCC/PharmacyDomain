"""変更が無いときに保存を行わないことのテスト。

同値判定は集約ではなくユースケース側に一本化している。集約の ``change_*`` は
常に差し替えるだけなので、「無駄な保存をしない」保証はこの層のテストで担保する。
"""

from __future__ import annotations

import pytest

from app.application.store import (
    ChangeInsurancePharmacyNumberCommand,
    ChangeInsurancePharmacyNumberUseCase,
    ChangeStoreAddressCommand,
    ChangeStoreAddressUseCase,
    ChangeStoreCodeCommand,
    ChangeStoreCodeUseCase,
    ChangeStoreContactInfoCommand,
    ChangeStoreContactInfoUseCase,
    ChangeStoreNamesCommand,
    ChangeStoreNamesUseCase,
)
from app.domain.corporate import CorporateId
from app.domain.store import (
    InsurancePharmacyNumberUniquenessService,
    StoreCodeUniquenessService,
    StoreNameUniquenessService,
)
from tests.application.access_helpers import create_vendor_corporate_access
from tests.application.store.helpers import save_store
from tests.factories.store_factory import VALID_INSURANCE_NUMBER
from tests.fakes.in_memory_store_repository import InMemoryStoreRepository


async def test_change_names_skips_save_when_nothing_changed() -> None:
    # Arrange
    repository = InMemoryStoreRepository()
    corporate_id = CorporateId.generate()
    store = await save_store(repository, corporate_id=corporate_id)
    use_case = ChangeStoreNamesUseCase(
        repository,
        StoreNameUniquenessService(repository),
        create_vendor_corporate_access(),
    )
    repository.save_count = 0

    # Act: 現在と同じ名称一式を渡す
    await use_case.execute(
        ChangeStoreNamesCommand(
            corporate_id=str(corporate_id.value),
            store_id=str(store.id.value),
            new_name="サンプル薬局",
            new_name_kana="サンプルヤッキョク",
        )
    )

    # Assert
    assert repository.save_count == 0


async def test_change_address_skips_save_when_nothing_changed() -> None:
    # Arrange
    repository = InMemoryStoreRepository()
    corporate_id = CorporateId.generate()
    store = await save_store(repository, corporate_id=corporate_id)
    use_case = ChangeStoreAddressUseCase(
        repository,
        create_vendor_corporate_access(),
    )
    repository.save_count = 0

    # Act
    await use_case.execute(
        ChangeStoreAddressCommand(
            corporate_id=str(corporate_id.value),
            store_id=str(store.id.value),
            postal_code="1234567",
            address="東京都千代田区1-2-3",
        )
    )

    # Assert
    assert repository.save_count == 0


async def test_change_contact_info_skips_save_when_nothing_changed() -> None:
    # Arrange
    repository = InMemoryStoreRepository()
    corporate_id = CorporateId.generate()
    store = await save_store(repository, corporate_id=corporate_id)
    use_case = ChangeStoreContactInfoUseCase(
        repository,
        create_vendor_corporate_access(),
    )
    repository.save_count = 0

    # Act
    await use_case.execute(
        ChangeStoreContactInfoCommand(
            corporate_id=str(corporate_id.value),
            store_id=str(store.id.value),
            phone_number="0312345678",
        )
    )

    # Assert
    assert repository.save_count == 0


async def test_change_code_skips_save_when_nothing_changed() -> None:
    # Arrange
    repository = InMemoryStoreRepository()
    corporate_id = CorporateId.generate()
    store = await save_store(repository, corporate_id=corporate_id, code="ST-001")
    use_case = ChangeStoreCodeUseCase(
        repository,
        StoreCodeUniquenessService(repository),
        create_vendor_corporate_access(),
    )
    repository.save_count = 0

    # Act
    await use_case.execute(
        ChangeStoreCodeCommand(
            corporate_id=str(corporate_id.value),
            store_id=str(store.id.value),
            new_code="ST-001",
        )
    )

    # Assert
    assert repository.save_count == 0


@pytest.mark.parametrize("blank", [None, "", "   "])
async def test_change_insurance_number_skips_save_when_already_unset(
    blank: str | None,
) -> None:
    # Arrange: 未設定の店舗に対する「解除」は変更なしとみなす
    repository = InMemoryStoreRepository()
    corporate_id = CorporateId.generate()
    store = await save_store(repository, corporate_id=corporate_id)
    use_case = ChangeInsurancePharmacyNumberUseCase(
        repository,
        InsurancePharmacyNumberUniquenessService(repository),
        create_vendor_corporate_access(),
    )
    repository.save_count = 0

    # Act
    await use_case.execute(
        ChangeInsurancePharmacyNumberCommand(
            corporate_id=str(corporate_id.value),
            store_id=str(store.id.value),
            new_number=blank,
        )
    )

    # Assert
    assert repository.save_count == 0


async def test_change_insurance_number_saves_when_value_actually_changes() -> None:
    # Arrange: 対照として、実際に変わるときは保存されること
    repository = InMemoryStoreRepository()
    corporate_id = CorporateId.generate()
    store = await save_store(repository, corporate_id=corporate_id)
    use_case = ChangeInsurancePharmacyNumberUseCase(
        repository,
        InsurancePharmacyNumberUniquenessService(repository),
        create_vendor_corporate_access(),
    )
    repository.save_count = 0

    # Act
    await use_case.execute(
        ChangeInsurancePharmacyNumberCommand(
            corporate_id=str(corporate_id.value),
            store_id=str(store.id.value),
            new_number=VALID_INSURANCE_NUMBER,
        )
    )

    # Assert
    assert repository.save_count == 1
