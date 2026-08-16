import pytest

from app.domain.corporate import (
    Corporate,
    CorporateName,
    CorporateNameAlreadyExistsError,
    CorporateNameUniquenessService,
    CorporateRepresentativeName,
)
from tests.fakes.in_memory_corporate_repository import InMemoryCorporateRepository


def create_representative() -> CorporateRepresentativeName:
    """テスト用代表者名のヘルパー関数"""
    return CorporateRepresentativeName.create(
        last_name="山田",
        first_name="太郎",
    )


@pytest.mark.asyncio
async def test_ensure_name_is_unique_passes_when_name_does_not_exist() -> None:
    # Arrange: 空のリポジトリとサービスを用意
    repository = InMemoryCorporateRepository()
    service = CorporateNameUniquenessService(repository)
    new_name = CorporateName("新規テスト法人")

    # Act
    await service.ensure_name_is_unique(name=new_name)

    # Assert
    assert await repository.exists_by_name(new_name) is False


@pytest.mark.asyncio
async def test_ensure_name_is_unique_raises_error_when_name_already_exists() -> None:
    # Arrange: あらかじめリポジトリに法人を1件登録しておく
    repository = InMemoryCorporateRepository()
    existing_name = CorporateName("既存テスト法人")
    existing_corporate = Corporate.create(
        name=existing_name,
        representative_name=create_representative(),
    )
    await repository.save(existing_corporate)

    service = CorporateNameUniquenessService(repository)

    # Act
    with pytest.raises(CorporateNameAlreadyExistsError) as exc_info:
        await service.ensure_name_is_unique(name=existing_name)

    # Assert
    assert f"法人名 '{existing_name.value}' は既に登録されています。" in str(
        exc_info.value
    )


@pytest.mark.asyncio
async def test_ensure_name_is_unique_allows_the_current_corporate_name() -> None:
    # Arrange
    repository = InMemoryCorporateRepository()
    existing_name = CorporateName("既存テスト法人")
    existing_corporate = Corporate.create(
        name=existing_name,
        representative_name=create_representative(),
    )
    await repository.save(existing_corporate)

    service = CorporateNameUniquenessService(repository)

    # Act
    await service.ensure_name_is_unique(
        name=existing_name,
        excluding_id=existing_corporate.id,
    )

    # Assert
    assert (
        await repository.exists_by_name(
            existing_name,
            excluding_id=existing_corporate.id,
        )
        is False
    )
