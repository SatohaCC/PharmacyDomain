"""店舗コンテキストのユースケース束。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.corporate.corporate_access import CorporateAccessService
from app.application.store.change_insurance_pharmacy_number import (
    ChangeInsurancePharmacyNumberUseCase,
)
from app.application.store.change_store_address import ChangeStoreAddressUseCase
from app.application.store.change_store_code import ChangeStoreCodeUseCase
from app.application.store.change_store_contact_info import (
    ChangeStoreContactInfoUseCase,
)
from app.application.store.change_store_name import ChangeStoreNamesUseCase
from app.application.store.get_store import GetStoreUseCase
from app.application.store.list_stores import ListStoresUseCase
from app.application.store.register_store import RegisterStoreUseCase
from app.domain.store.services import (
    InsurancePharmacyNumberUniquenessService,
    StoreCodeUniquenessService,
    StoreNameUniquenessService,
)
from app.infrastructure.composition.repositories import PostgresRepositorySet


@dataclass(frozen=True, slots=True)
class StoreUseCases:
    """店舗コンテキストのユースケース。"""

    register: RegisterStoreUseCase
    get: GetStoreUseCase
    list_by_corporate: ListStoresUseCase
    change_names: ChangeStoreNamesUseCase
    change_code: ChangeStoreCodeUseCase
    change_address: ChangeStoreAddressUseCase
    change_contact_info: ChangeStoreContactInfoUseCase
    change_insurance_pharmacy_number: ChangeInsurancePharmacyNumberUseCase


def build_store_use_cases(
    repositories: PostgresRepositorySet,
    corporate_access: CorporateAccessService,
) -> StoreUseCases:
    """店舗ユースケースを組み立てる。"""
    repository = repositories.store
    name_uniqueness = StoreNameUniquenessService(repository)
    code_uniqueness = StoreCodeUniquenessService(repository)
    number_uniqueness = InsurancePharmacyNumberUniquenessService(repository)
    return StoreUseCases(
        register=RegisterStoreUseCase(
            repository,
            name_uniqueness,
            code_uniqueness,
            number_uniqueness,
            corporate_access,
        ),
        get=GetStoreUseCase(repository, corporate_access),
        list_by_corporate=ListStoresUseCase(repository, corporate_access),
        change_names=ChangeStoreNamesUseCase(
            repository, name_uniqueness, corporate_access
        ),
        change_code=ChangeStoreCodeUseCase(
            repository, code_uniqueness, corporate_access
        ),
        change_address=ChangeStoreAddressUseCase(repository, corporate_access),
        change_contact_info=ChangeStoreContactInfoUseCase(repository, corporate_access),
        change_insurance_pharmacy_number=ChangeInsurancePharmacyNumberUseCase(
            repository, number_uniqueness, corporate_access
        ),
    )
