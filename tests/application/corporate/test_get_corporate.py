from __future__ import annotations

import pytest

from app.application.corporate import CorporateNotFoundError
from app.application.corporate.get_corporate import (
    CorporateResponseDto,
    GetCorporateUseCase,
)
from app.base.domain.exceptions import DomainValidationError
from tests.application.access_helpers import create_vendor_corporate_access_for
from tests.application.corporate.helpers import create_corporate, save_corporate
from tests.fakes.in_memory_corporate_repository import InMemoryCorporateRepository


@pytest.mark.asyncio
async def test_get_corporate_returns_response_dto() -> None:
    # Arrange
    repository = InMemoryCorporateRepository()
    corporate = await save_corporate(repository)
    use_case = GetCorporateUseCase(create_vendor_corporate_access_for(repository))

    # Act
    actual = await use_case.execute(str(corporate.id.value))

    # Assert
    assert actual == CorporateResponseDto(
        id=str(corporate.id.value),
        name="テスト法人",
        representative_name="山田 太郎",
        is_active=True,
    )


@pytest.mark.asyncio
async def test_get_corporate_raises_when_corporate_does_not_exist() -> None:
    # Arrange
    repository = InMemoryCorporateRepository()
    use_case = GetCorporateUseCase(create_vendor_corporate_access_for(repository))
    missing_id = str(create_corporate("一時法人").id.value)

    # Act / Assert
    with pytest.raises(CorporateNotFoundError):
        await use_case.execute(missing_id)


@pytest.mark.asyncio
async def test_get_corporate_raises_validation_error_for_malformed_id() -> None:
    # Arrange: 未検出（404相当）と入力値エラー（400相当）が区別されることを確認する
    repository = InMemoryCorporateRepository()
    use_case = GetCorporateUseCase(create_vendor_corporate_access_for(repository))

    # Act / Assert
    with pytest.raises(DomainValidationError):
        await use_case.execute("not-a-uuid")
