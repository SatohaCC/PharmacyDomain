"""店舗登録ユースケースのテスト。"""

from __future__ import annotations

import pytest

from app.application.corporate import CorporateInactiveError
from app.application.store import RegisterStoreCommand, RegisterStoreUseCase
from app.domain.corporate import CorporateId
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.store import (
    InsurancePharmacyNumberAlreadyExistsError,
    InsurancePharmacyNumberUniquenessService,
    StoreCodeAlreadyExistsError,
    StoreCodeUniquenessService,
    StoreNameAlreadyExistsError,
    StoreNameUniquenessService,
)
from tests.application.access_helpers import (
    AutoProvisioningCorporateRepository,
    create_vendor_corporate_access,
    create_vendor_corporate_access_for,
)
from tests.application.store.helpers import save_store
from tests.factories.store_factory import VALID_INSURANCE_NUMBER
from tests.fakes.in_memory_store_repository import InMemoryStoreRepository


def create_use_case(repository: InMemoryStoreRepository) -> RegisterStoreUseCase:
    return RegisterStoreUseCase(
        repository,
        StoreNameUniquenessService(repository),
        StoreCodeUniquenessService(repository),
        InsurancePharmacyNumberUniquenessService(repository),
        create_vendor_corporate_access(),
    )


def create_command(
    corporate_id: CorporateId,
    *,
    name: str = "サンプル薬局",
    name_kana: str = "サンプルヤッキョク",
    name_romaji: str | None = None,
    code: str | None = None,
    fax_number: str | None = None,
    email: str | None = None,
    insurance_pharmacy_number: str | None = None,
) -> RegisterStoreCommand:
    return RegisterStoreCommand(
        corporate_id=str(corporate_id.value),
        name=name,
        name_kana=name_kana,
        name_romaji=name_romaji,
        postal_code="1234567",
        address="東京都千代田区1-2-3",
        phone_number="03-1234-5678",
        fax_number=fax_number,
        email=email,
        code=code,
        insurance_pharmacy_number=insurance_pharmacy_number,
    )


async def test_register_store_returns_id_and_persists_store() -> None:
    # Arrange
    repository = InMemoryStoreRepository()
    use_case = create_use_case(repository)
    corporate_id = CorporateId.generate()
    command = create_command(
        corporate_id, code="ST-001", insurance_pharmacy_number=VALID_INSURANCE_NUMBER
    )

    # Act
    store_id = await use_case.execute(command)

    # Assert
    actual = await repository.get(store_id)
    assert actual is not None
    assert actual.corporate_id == corporate_id
    assert actual.names.name.value == "サンプル薬局"
    assert actual.address.postal_code.value == "123-4567"
    assert actual.contact_info.phone_number.value == "0312345678"
    assert actual.code is not None
    assert actual.code.value == "ST-001"
    assert actual.insurance_pharmacy_number is not None
    assert actual.insurance_pharmacy_number.value == VALID_INSURANCE_NUMBER


async def test_register_store_rejects_inactive_corporate() -> None:
    # Arrange
    repository = InMemoryStoreRepository()
    corporate_id = CorporateId.generate()
    corporate_repository = AutoProvisioningCorporateRepository()
    corporate_repository.set_inactive(corporate_id)
    use_case = RegisterStoreUseCase(
        repository,
        StoreNameUniquenessService(repository),
        StoreCodeUniquenessService(repository),
        InsurancePharmacyNumberUniquenessService(repository),
        create_vendor_corporate_access_for(corporate_repository),
    )

    # Act & Assert
    with pytest.raises(CorporateInactiveError):
        await use_case.execute(create_command(corporate_id))

    assert await repository.list_all() == []


async def test_register_store_accepts_kana_starting_with_small_a() -> None:
    # Arrange: 「ファーマシー」を含む店舗名が登録できることを保証する
    repository = InMemoryStoreRepository()
    use_case = create_use_case(repository)
    command = create_command(
        CorporateId.generate(),
        name="ファーマシーサンプル",
        name_kana="ファーマシーサンプル",
    )

    # Act
    store_id = await use_case.execute(command)

    # Assert
    actual = await repository.get(store_id)
    assert actual is not None
    assert actual.names.kana.value == "ファーマシーサンプル"


@pytest.mark.parametrize("blank", ["", "   "])
async def test_register_store_treats_blank_optional_values_as_unset(
    blank: str,
) -> None:
    # Arrange
    repository = InMemoryStoreRepository()
    use_case = create_use_case(repository)
    command = create_command(
        CorporateId.generate(),
        name_romaji=blank,
        code=blank,
        fax_number=blank,
        email=blank,
        insurance_pharmacy_number=blank,
    )

    # Act
    store_id = await use_case.execute(command)

    # Assert
    actual = await repository.get(store_id)
    assert actual is not None
    assert actual.names.romaji is None
    assert actual.code is None
    assert actual.contact_info.fax_number is None
    assert actual.contact_info.email is None
    assert actual.insurance_pharmacy_number is None


async def test_register_store_rejects_duplicate_name_in_same_corporate() -> None:
    # Arrange
    repository = InMemoryStoreRepository()
    corporate_id = CorporateId.generate()
    await save_store(repository, corporate_id=corporate_id, name="サンプル薬局")
    use_case = create_use_case(repository)

    # Act
    with pytest.raises(StoreNameAlreadyExistsError):
        await use_case.execute(create_command(corporate_id, name="サンプル薬局"))

    # Assert: 2件目が保存されていないこと
    assert len(await repository.list_by_corporate_id(corporate_id)) == 1


async def test_register_store_allows_duplicate_name_in_another_corporate() -> None:
    # Arrange: 店舗名の一意性は法人単位で閉じている
    repository = InMemoryStoreRepository()
    existing_corporate_id = CorporateId.generate()
    await save_store(
        repository, corporate_id=existing_corporate_id, name="サンプル薬局"
    )
    use_case = create_use_case(repository)
    other_corporate_id = CorporateId.generate()

    # Act
    store_id = await use_case.execute(
        create_command(other_corporate_id, name="サンプル薬局")
    )

    # Assert
    assert len(await repository.list_by_corporate_id(other_corporate_id)) == 1
    actual = await repository.get(store_id)
    assert actual is not None
    assert actual.corporate_id == other_corporate_id


async def test_register_store_rejects_duplicate_code_in_same_corporate() -> None:
    # Arrange
    repository = InMemoryStoreRepository()
    corporate_id = CorporateId.generate()
    await save_store(
        repository, corporate_id=corporate_id, name="既存薬局", code="ST-001"
    )
    use_case = create_use_case(repository)

    # Act
    with pytest.raises(StoreCodeAlreadyExistsError):
        await use_case.execute(
            create_command(corporate_id, name="サンプル薬局", code="ST-001")
        )

    # Assert
    assert len(await repository.list_by_corporate_id(corporate_id)) == 1


async def test_register_store_rejects_duplicate_insurance_number() -> None:
    # Arrange: 指定番号は法人をまたいでも一意である
    repository = InMemoryStoreRepository()
    existing_corporate_id = CorporateId.generate()
    await save_store(
        repository,
        corporate_id=existing_corporate_id,
        insurance_pharmacy_number=VALID_INSURANCE_NUMBER,
    )
    use_case = create_use_case(repository)
    other_corporate_id = CorporateId.generate()

    # Act / Assert
    with pytest.raises(InsurancePharmacyNumberAlreadyExistsError):
        await use_case.execute(
            create_command(
                other_corporate_id,
                insurance_pharmacy_number=VALID_INSURANCE_NUMBER,
            )
        )

    assert len(await repository.list_all()) == 1


async def test_register_store_rejects_invalid_kana_without_persisting() -> None:
    # Arrange
    repository = InMemoryStoreRepository()
    use_case = create_use_case(repository)
    command = create_command(CorporateId.generate(), name_kana="さんぷるやっきょく")

    # Act
    with pytest.raises(DomainValidationError):
        await use_case.execute(command)

    # Assert
    assert await repository.list_all() == []


async def test_register_store_rejects_malformed_corporate_id() -> None:
    # Arrange
    repository = InMemoryStoreRepository()
    use_case = create_use_case(repository)
    command = RegisterStoreCommand(
        corporate_id="not-a-uuid",
        name="サンプル薬局",
        name_kana="サンプルヤッキョク",
        postal_code="1234567",
        address="東京都千代田区1-2-3",
        phone_number="0312345678",
    )

    # Act / Assert
    with pytest.raises(DomainValidationError):
        await use_case.execute(command)
