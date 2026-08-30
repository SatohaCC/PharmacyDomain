from __future__ import annotations

import pytest

from app.application.access_control import ActorContext, AuthorizationService
from app.application.common.exceptions import AuthorizationError
from app.application.corporate import CorporateAccessService
from app.application.corporate.register_corporate import (
    RegisterCorporateCommand,
    RegisterCorporateUseCase,
)
from app.domain.corporate import (
    CorporateId,
    CorporateNameAlreadyExistsError,
    CorporateNameUniquenessService,
)
from app.domain.foundation.exceptions import DomainValidationError
from tests.application.access_helpers import create_vendor_corporate_access_for
from tests.fakes.in_memory_corporate_repository import InMemoryCorporateRepository


def create_command(name: str = "株式会社テスト") -> RegisterCorporateCommand:
    return RegisterCorporateCommand(
        name=name,
        representative_last_name="山田",
        representative_first_name="太郎",
    )


def create_use_case(
    repository: InMemoryCorporateRepository,
) -> RegisterCorporateUseCase:
    return RegisterCorporateUseCase(
        repository,
        CorporateNameUniquenessService(repository),
        create_vendor_corporate_access_for(repository),
    )


@pytest.mark.asyncio
async def test_register_corporate_returns_id_and_persists_corporate() -> None:
    # Arrange
    repository = InMemoryCorporateRepository()
    use_case = create_use_case(repository)
    command = create_command()

    # Act
    corporate_id = await use_case.execute(command)

    # Assert
    actual = await repository.get(corporate_id)
    assert actual is not None
    assert actual.name.value == command.name
    assert actual.representative_name.full_name == "山田 太郎"


@pytest.mark.asyncio
async def test_register_corporate_rejects_duplicate_name_without_second_record() -> (
    None
):
    # Arrange
    repository = InMemoryCorporateRepository()
    use_case = create_use_case(repository)
    command = create_command()
    await use_case.execute(command)

    # Act
    with pytest.raises(CorporateNameAlreadyExistsError):
        await use_case.execute(command)

    # Assert
    assert len(await repository.list_all()) == 1


@pytest.mark.asyncio
async def test_register_corporate_rejects_invalid_name_without_persisting() -> None:
    # Arrange
    repository = InMemoryCorporateRepository()
    use_case = create_use_case(repository)
    command = create_command(name="   ")

    # Act
    with pytest.raises(DomainValidationError):
        await use_case.execute(command)

    # Assert
    assert await repository.list_all() == []


@pytest.mark.asyncio
async def test_register_corporate_rejects_corporate_admin() -> None:
    repository = InMemoryCorporateRepository()
    corporate_access = CorporateAccessService(
        repository,
        AuthorizationService(
            ActorContext.corporate_admin(
                principal_id="corp-admin-1",
                corporate_id=CorporateId.generate(),
            )
        ),
    )
    use_case = RegisterCorporateUseCase(
        repository,
        CorporateNameUniquenessService(repository),
        corporate_access,
    )

    with pytest.raises(AuthorizationError):
        await use_case.execute(create_command())
