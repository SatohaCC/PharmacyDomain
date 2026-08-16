from __future__ import annotations

import pytest

from app.application.corporate.change_corporate_name import (
    ChangeCorporateNameCommand,
    ChangeCorporateNameUseCase,
)
from app.domain.corporate import (
    CorporateNameAlreadyExistsError,
    CorporateNameUniquenessService,
)
from tests.application.access_helpers import create_vendor_corporate_access_for
from tests.application.corporate.helpers import save_corporate
from tests.fakes.in_memory_corporate_repository import InMemoryCorporateRepository


@pytest.mark.asyncio
async def test_change_corporate_name_updates_and_persists_corporate() -> None:
    # Arrange
    repository = InMemoryCorporateRepository()
    corporate = await save_corporate(repository)
    use_case = ChangeCorporateNameUseCase(
        repository,
        CorporateNameUniquenessService(repository),
        create_vendor_corporate_access_for(repository),
    )

    # Act
    await use_case.execute(
        ChangeCorporateNameCommand(
            corporate_id=str(corporate.id.value),
            new_name="変更後法人",
        )
    )

    # Assert
    actual = await repository.get(corporate.id)
    assert actual is not None
    assert actual.name.value == "変更後法人"


@pytest.mark.asyncio
async def test_change_corporate_name_rejects_another_corporates_name() -> None:
    # Arrange
    repository = InMemoryCorporateRepository()
    first = await save_corporate(repository, "最初の法人")
    await save_corporate(repository, "別の法人")
    use_case = ChangeCorporateNameUseCase(
        repository,
        CorporateNameUniquenessService(repository),
        create_vendor_corporate_access_for(repository),
    )

    # Act / Assert
    with pytest.raises(CorporateNameAlreadyExistsError):
        await use_case.execute(
            ChangeCorporateNameCommand(
                corporate_id=str(first.id.value),
                new_name="別の法人",
            )
        )
