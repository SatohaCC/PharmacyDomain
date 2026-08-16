from __future__ import annotations

from app.domain.corporate import Corporate, CorporateName, CorporateRepresentativeName
from tests.fakes.in_memory_corporate_repository import InMemoryCorporateRepository


def create_representative(
    last_name: str = "山田", first_name: str = "太郎"
) -> CorporateRepresentativeName:
    return CorporateRepresentativeName.create(
        last_name=last_name,
        first_name=first_name,
    )


def create_corporate(name: str = "テスト法人") -> Corporate:
    return Corporate.create(
        name=CorporateName(name),
        representative_name=create_representative(),
    )


async def save_corporate(
    repository: InMemoryCorporateRepository,
    name: str = "テスト法人",
) -> Corporate:
    corporate = create_corporate(name)
    await repository.save(corporate)
    return corporate
