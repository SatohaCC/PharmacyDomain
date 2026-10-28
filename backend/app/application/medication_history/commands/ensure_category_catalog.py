"""Applicationのensure_category_catalogを定義する。"""

from __future__ import annotations

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.medication_history.commands.dtos.category_catalog import (
    CategoryCatalogDto,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.medication_history.entities import MedicationHistoryCategoryCatalog
from app.domain.medication_history.repositories import (
    MedicationHistoryCategoryCatalogRepository,
)


class EnsureCategoryCatalogUseCase:
    """法人の薬歴記載区分カタログを取得するユースケース。"""

    def __init__(
        self,
        repository: MedicationHistoryCategoryCatalogRepository,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access

    async def execute(self, corporate_id: str) -> CategoryCatalogDto:
        """区分カタログを取得する。未作成の場合はデフォルトを生成して保存・返却する。"""
        parsed_corporate_id = CorporateId.parse(corporate_id)
        await self._corporate_access.require_active(
            corporate_id=parsed_corporate_id,
            permission=Permission.MANAGE_MEDICATION_HISTORY,
        )
        catalog = await self._repository.get(corporate_id=parsed_corporate_id)
        if catalog is None:
            catalog = MedicationHistoryCategoryCatalog.create_default(
                corporate_id=parsed_corporate_id
            )
            await self._repository.save(catalog)
        return CategoryCatalogDto.from_entity(catalog)
