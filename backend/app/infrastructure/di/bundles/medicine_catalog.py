"""医薬品マスタコンテキストのユースケース束。"""

from __future__ import annotations

from app.application.access_control.policies import AuthorizationService
from app.application.composition.registry import MedicineCatalogUseCases
from app.application.medicine_catalog.commands.import_yj_catalog import (
    ImportYjCatalogUseCase,
)
from app.application.medicine_catalog.commands.register_medicine import (
    RegisterMedicineUseCase,
)
from app.application.medicine_catalog.queries.get_effective_medicine import (
    GetEffectiveMedicineUseCase,
)
from app.domain.medicine_catalog.services import MedicineEffectivePeriodConflictService
from app.infrastructure.di.repositories import (
    PostgresRepositorySet,
)
from app.infrastructure.readers.medicine_catalog_get_effective_medicine import (
    GetEffectiveMedicineProjection,
)


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
        get_effective=GetEffectiveMedicineUseCase(
            reader=GetEffectiveMedicineProjection(repository),
            authorization=authorization,
        ),
        import_yj=ImportYjCatalogUseCase(repository, authorization),
    )


__all__ = [
    "MedicineCatalogUseCases",
    "build_medicine_catalog_use_cases",
]
