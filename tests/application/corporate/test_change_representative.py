from __future__ import annotations

import pytest

from app.application.corporate.change_representative import (
    ChangeRepresentativeCommand,
    ChangeRepresentativeUseCase,
)
from tests.application.access_helpers import create_vendor_corporate_access_for
from tests.application.corporate.helpers import save_corporate
from tests.fakes.in_memory_corporate_repository import InMemoryCorporateRepository


@pytest.mark.asyncio
async def test_change_representative_updates_and_persists_corporate() -> None:
    # Arrange
    repository = InMemoryCorporateRepository()
    corporate = await save_corporate(repository)
    use_case = ChangeRepresentativeUseCase(
        repository,
        create_vendor_corporate_access_for(repository),
    )

    # Act
    await use_case.execute(
        ChangeRepresentativeCommand(
            corporate_id=str(corporate.id.value),
            new_last_name="佐藤",
            new_first_name="花子",
        )
    )

    # Assert
    actual = await repository.get(corporate.id)
    assert actual is not None
    assert actual.representative_name.full_name == "佐藤 花子"


@pytest.mark.asyncio
async def test_change_representative_skips_save_when_nothing_changed() -> None:
    # Arrange: 同値判定はユースケース側に一本化しているため、ここで保証する
    repository = InMemoryCorporateRepository()
    corporate = await save_corporate(repository)
    use_case = ChangeRepresentativeUseCase(
        repository,
        create_vendor_corporate_access_for(repository),
    )
    repository.save_count = 0

    # Act: 現在と同じ代表者名を渡す
    await use_case.execute(
        ChangeRepresentativeCommand(
            corporate_id=str(corporate.id.value),
            new_last_name="山田",
            new_first_name="太郎",
        )
    )

    # Assert
    assert repository.save_count == 0
