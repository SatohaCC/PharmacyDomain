"""医薬品マスタコンテキストのユースケース束。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control.policy import AuthorizationService
from app.application.medicine_catalog.get_medicine import GetEffectiveMedicineUseCase
from app.application.medicine_catalog.register_medicine import RegisterMedicineUseCase
from app.domain.medicine_catalog.services import MedicineEffectivePeriodConflictService
from app.infrastructure.composition.repositories import PostgresRepositorySet


@dataclass(frozen=True, slots=True)
class MedicineCatalogUseCases:
    """医薬品マスタコンテキストのユースケース。"""

    register: RegisterMedicineUseCase
    get_effective: GetEffectiveMedicineUseCase


def build_medicine_catalog_use_cases(
    repositories: PostgresRepositorySet,
    authorization: AuthorizationService,
) -> MedicineCatalogUseCases:
    """医薬品マスタユースケースを組み立てる。

    薬価基準は法人ごとに内容が違わないので、対象法人を伴う
    ``CorporateAccessService`` ではなく ``AuthorizationService`` を直接使う。
    取り込みはベンダーシステム管理者専用である。
    """
    repository = repositories.medicine_catalog
    return MedicineCatalogUseCases(
        register=RegisterMedicineUseCase(
            repository, authorization, MedicineEffectivePeriodConflictService()
        ),
        get_effective=GetEffectiveMedicineUseCase(repository, authorization),
    )
