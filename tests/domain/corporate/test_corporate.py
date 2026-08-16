from __future__ import annotations

import importlib
import uuid

import pytest

from app.base.domain.exceptions import DomainValidationError
from app.domain.corporate import (
    Corporate,
    CorporateCatalogRepository,
    CorporateId,
    CorporateName,
    CorporateNameAlreadyExistsError,
    CorporateRepository,
    CorporateRepresentativeName,
)
from tests.fakes.in_memory_corporate_repository import InMemoryCorporateRepository


def representative(
    last_name: str = "山田", first_name: str = "太郎"
) -> CorporateRepresentativeName:
    return CorporateRepresentativeName.create(
        last_name=last_name,
        first_name=first_name,
    )


def test_create_generates_uuid7_and_normalizes_name() -> None:
    # Arrange
    name = CorporateName("  株式会社  テスト  ")
    representative_name = representative()

    # Act
    corporate = Corporate.create(
        name=name,
        representative_name=representative_name,
    )

    # Assert
    assert corporate.id.value.version == 7
    assert corporate.name.value == "株式会社 テスト"
    assert corporate.representative_name.full_name == "山田 太郎"


@pytest.mark.parametrize(
    ("value", "expected_message"),
    [
        ("", "法人名は空にできません。"),
        ("   ", "法人名は空にできません。"),
        ("x" * 101, "法人名は100文字以内で指定してください。"),
    ],
)
def test_corporate_name_rejects_invalid_values(
    value: str, expected_message: str
) -> None:
    # Arrange: value is supplied by pytest.parametrize.
    # Act / Assert
    with pytest.raises(DomainValidationError) as exc_info:
        CorporateName(value)

    assert str(exc_info.value) == expected_message


@pytest.mark.parametrize(
    ("last_name", "first_name"),
    [("", "太郎"), ("山田", "")],
)
def test_representative_name_rejects_empty_parts(
    last_name: str, first_name: str
) -> None:
    # Arrange: names are supplied by pytest.parametrize.
    # Act / Assert
    with pytest.raises(DomainValidationError):
        representative(last_name, first_name)


def test_change_name_updates_name() -> None:
    # Arrange
    corporate = Corporate.create(
        name=CorporateName("旧法人"),
        representative_name=representative(),
    )

    # Act
    corporate = corporate.change_name(CorporateName("新法人"))

    # Assert
    assert corporate.name.value == "新法人"


def test_change_representative_updates_representative() -> None:
    # Arrange
    corporate = Corporate.create(
        name=CorporateName("法人"),
        representative_name=representative(),
    )

    # Act
    corporate = corporate.change_representative(representative("佐藤", "花子"))

    # Assert
    assert corporate.representative_name.full_name == "佐藤 花子"


def test_change_name_is_noop_for_same_value() -> None:
    # Arrange
    original_name = CorporateName("法人")
    corporate = Corporate.create(
        name=original_name,
        representative_name=representative(),
    )

    # Act
    corporate.change_name(CorporateName("法人"))

    # Assert
    assert corporate.name == original_name


def test_corporate_id_parses_uuid7() -> None:
    # Arrange
    uuid7 = uuid.uuid7()

    # Act
    actual = CorporateId.parse(str(uuid7))

    # Assert
    assert actual.value == uuid7


def test_corporate_id_rejects_other_uuid_versions() -> None:
    # Arrange
    uuid4 = uuid.uuid4()

    # Act / Assert
    with pytest.raises(DomainValidationError):
        CorporateId.parse(str(uuid4))


def test_public_package_exports() -> None:
    # Arrange
    public_api = {
        CorporateRepresentativeName,
        CorporateCatalogRepository,
    }

    # Act
    module = importlib.import_module("app.domain.corporate")
    exported_names = set(getattr(module, "__all__", []))

    # Assert
    assert {item.__name__ for item in public_api} <= exported_names


@pytest.mark.asyncio
async def test_repository_save_and_get() -> None:
    # Arrange
    implementation = InMemoryCorporateRepository()
    repository: CorporateRepository = implementation
    corporate = Corporate.create(
        name=CorporateName("テスト法人"),
        representative_name=representative(),
    )

    # Act
    await repository.save(corporate)
    actual = await repository.get(corporate.id)

    # Assert
    assert actual == corporate


@pytest.mark.asyncio
async def test_repository_save_rejects_duplicate_name() -> None:
    # Arrange
    repository = InMemoryCorporateRepository()
    first = Corporate.create(
        name=CorporateName("テスト法人"),
        representative_name=representative(),
    )
    second = Corporate.create(
        name=CorporateName("テスト法人"),
        representative_name=representative("佐藤", "花子"),
    )
    await repository.save(first)

    # Act
    with pytest.raises(CorporateNameAlreadyExistsError):
        await repository.save(second)

    # Assert
    assert await repository.list_all() == [first]


@pytest.mark.asyncio
async def test_catalog_repository_lists_all_corporates() -> None:
    # Arrange
    implementation = InMemoryCorporateRepository()
    catalog: CorporateCatalogRepository = implementation
    corporate = Corporate.create(
        name=CorporateName("テスト法人"),
        representative_name=representative(),
    )
    await implementation.save(corporate)

    # Act
    actual = await catalog.list_all()

    # Assert
    assert actual == [corporate]


@pytest.mark.asyncio
async def test_repository_save_allows_updating_the_same_corporate() -> None:
    # Arrange
    repository = InMemoryCorporateRepository()
    corporate = Corporate.create(
        name=CorporateName("テスト法人"),
        representative_name=representative(),
    )
    await repository.save(corporate)

    # Act
    corporate = corporate.change_representative(representative("佐藤", "花子"))
    await repository.save(corporate)

    actual = await repository.get(corporate.id)

    # Assert
    assert actual is not None
    assert actual.representative_name.full_name == "佐藤 花子"
