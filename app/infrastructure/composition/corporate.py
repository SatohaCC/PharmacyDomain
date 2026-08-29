"""法人コンテキストのユースケース束。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.corporate.change_corporate_name import ChangeCorporateNameUseCase
from app.application.corporate.change_corporate_status import (
    ChangeCorporateStatusUseCase,
)
from app.application.corporate.change_representative import ChangeRepresentativeUseCase
from app.application.corporate.corporate_access import CorporateAccessService
from app.application.corporate.get_corporate import GetCorporateUseCase
from app.application.corporate.register_corporate import RegisterCorporateUseCase
from app.domain.corporate.services import CorporateNameUniquenessService
from app.infrastructure.composition.repositories import PostgresRepositorySet


@dataclass(frozen=True, slots=True)
class CorporateUseCases:
    """法人コンテキストのユースケース。"""

    register: RegisterCorporateUseCase
    get: GetCorporateUseCase
    change_name: ChangeCorporateNameUseCase
    change_representative: ChangeRepresentativeUseCase
    change_status: ChangeCorporateStatusUseCase


def build_corporate_use_cases(
    repositories: PostgresRepositorySet,
    corporate_access: CorporateAccessService,
) -> CorporateUseCases:
    """法人ユースケースを組み立てる。"""
    repository = repositories.corporate
    uniqueness = CorporateNameUniquenessService(repository)
    return CorporateUseCases(
        register=RegisterCorporateUseCase(repository, uniqueness, corporate_access),
        get=GetCorporateUseCase(corporate_access),
        change_name=ChangeCorporateNameUseCase(
            repository, uniqueness, corporate_access
        ),
        change_representative=ChangeRepresentativeUseCase(repository, corporate_access),
        change_status=ChangeCorporateStatusUseCase(repository, corporate_access),
    )
