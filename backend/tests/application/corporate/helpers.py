from __future__ import annotations

from app.domain.corporate.entities import Corporate
from app.domain.corporate.identifiers import CorporateId
from app.domain.corporate.primitives import CorporateName
from app.domain.corporate.value_objects import CorporateRepresentativeName
from app.domain.shared.person_name import PersonNamePart
from tests.fakes.in_memory_corporate_repository import InMemoryCorporateRepository


def create_representative(
    last_name: str = "山田", first_name: str = "太郎"
) -> CorporateRepresentativeName:
    return CorporateRepresentativeName(
        last_name=PersonNamePart(last_name), first_name=PersonNamePart(first_name)
    )


def create_corporate(name: str = "テスト法人") -> Corporate:
    return Corporate(
        id=CorporateId.generate(),
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
