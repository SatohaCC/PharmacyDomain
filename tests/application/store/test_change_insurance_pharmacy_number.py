"""保険薬局指定番号変更ユースケースのテスト。"""

from __future__ import annotations

import pytest

from app.application.store import (
    ChangeInsurancePharmacyNumberCommand,
    ChangeInsurancePharmacyNumberUseCase,
)
from app.application.store.exceptions import StoreNotFoundError
from app.base.domain.exceptions import DomainValidationError
from app.domain.corporate import CorporateId
from app.domain.store import InsurancePharmacyNumberUniquenessService
from app.domain.store.exceptions import InsurancePharmacyNumberAlreadyExistsError
from tests.application.access_helpers import create_vendor_corporate_access
from tests.application.store.helpers import save_store
from tests.factories.store_factory import VALID_INSURANCE_NUMBER
from tests.fakes.in_memory_store_repository import InMemoryStoreRepository


async def test_change_insurance_pharmacy_number_sets_number() -> None:
    # Arrange
    repository = InMemoryStoreRepository()
    corporate_id = CorporateId.generate()
    store = await save_store(repository, corporate_id=corporate_id)
    use_case = ChangeInsurancePharmacyNumberUseCase(
        repository,
        InsurancePharmacyNumberUniquenessService(repository),
        create_vendor_corporate_access(),
    )

    # Act
    await use_case.execute(
        ChangeInsurancePharmacyNumberCommand(
            corporate_id=str(corporate_id.value),
            store_id=str(store.id.value),
            new_number=VALID_INSURANCE_NUMBER,
        )
    )

    # Assert
    actual = await repository.get(store.id)
    assert actual is not None
    assert actual.insurance_pharmacy_number is not None
    assert actual.insurance_pharmacy_number.value == VALID_INSURANCE_NUMBER


@pytest.mark.parametrize("cleared", [None, "", "   "])
async def test_change_insurance_pharmacy_number_clears_number(
    cleared: str | None,
) -> None:
    # Arrange: None・空文字・空白のみは、いずれも「解除」として同じ結果になる
    repository = InMemoryStoreRepository()
    corporate_id = CorporateId.generate()
    store = await save_store(
        repository,
        corporate_id=corporate_id,
        insurance_pharmacy_number=VALID_INSURANCE_NUMBER,
    )
    use_case = ChangeInsurancePharmacyNumberUseCase(
        repository,
        InsurancePharmacyNumberUniquenessService(repository),
        create_vendor_corporate_access(),
    )

    # Act
    await use_case.execute(
        ChangeInsurancePharmacyNumberCommand(
            corporate_id=str(corporate_id.value),
            store_id=str(store.id.value),
            new_number=cleared,
        )
    )

    # Assert
    actual = await repository.get(store.id)
    assert actual is not None
    assert actual.insurance_pharmacy_number is None


async def test_change_insurance_pharmacy_number_rejects_invalid_number() -> None:
    # Arrange
    repository = InMemoryStoreRepository()
    corporate_id = CorporateId.generate()
    store = await save_store(repository, corporate_id=corporate_id)
    use_case = ChangeInsurancePharmacyNumberUseCase(
        repository,
        InsurancePharmacyNumberUniquenessService(repository),
        create_vendor_corporate_access(),
    )

    # Act: 3桁目の調剤区分が '4' でない番号
    with pytest.raises(DomainValidationError):
        await use_case.execute(
            ChangeInsurancePharmacyNumberCommand(
                corporate_id=str(corporate_id.value),
                store_id=str(store.id.value),
                new_number="1311234567",
            )
        )

    # Assert
    actual = await repository.get(store.id)
    assert actual is not None
    assert actual.insurance_pharmacy_number is None


async def test_change_insurance_pharmacy_number_rejects_store_of_another_corporate() -> (
    None
):
    # Arrange
    repository = InMemoryStoreRepository()
    store = await save_store(repository, corporate_id=CorporateId.generate())
    use_case = ChangeInsurancePharmacyNumberUseCase(
        repository,
        InsurancePharmacyNumberUniquenessService(repository),
        create_vendor_corporate_access(),
    )

    # Act / Assert
    with pytest.raises(StoreNotFoundError):
        await use_case.execute(
            ChangeInsurancePharmacyNumberCommand(
                corporate_id=str(CorporateId.generate().value),
                store_id=str(store.id.value),
                new_number=VALID_INSURANCE_NUMBER,
            )
        )


async def test_change_insurance_pharmacy_number_rejects_duplicate_number() -> None:
    # Arrange: 指定番号は法人をまたいでも一意である
    repository = InMemoryStoreRepository()
    first_corporate_id = CorporateId.generate()
    second_corporate_id = CorporateId.generate()
    await save_store(
        repository,
        corporate_id=first_corporate_id,
        insurance_pharmacy_number=VALID_INSURANCE_NUMBER,
    )
    second_store = await save_store(repository, corporate_id=second_corporate_id)
    use_case = ChangeInsurancePharmacyNumberUseCase(
        repository,
        InsurancePharmacyNumberUniquenessService(repository),
        create_vendor_corporate_access(),
    )

    # Act / Assert
    with pytest.raises(InsurancePharmacyNumberAlreadyExistsError):
        await use_case.execute(
            ChangeInsurancePharmacyNumberCommand(
                corporate_id=str(second_corporate_id.value),
                store_id=str(second_store.id.value),
                new_number=VALID_INSURANCE_NUMBER,
            )
        )

    actual = await repository.get(second_store.id)
    assert actual is not None
    assert actual.insurance_pharmacy_number is None
