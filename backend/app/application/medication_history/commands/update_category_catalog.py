"""Applicationのupdate_category_catalogを定義する。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.medication_history.commands.dtos.category_catalog import (
    CategoryCatalogDto,
)
from app.application.medication_history.commands.models import (
    MajorCategoryInput,
    MediumCategoryInput,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.medication_history.entities import MedicationHistoryCategoryCatalog
from app.domain.medication_history.identifiers import CategoryCatalogId
from app.domain.medication_history.primitives import (
    CategoryDisplayOrder,
    MajorCategoryCode,
    MajorCategoryName,
    MediumCategoryCode,
    MediumCategoryName,
)
from app.domain.medication_history.repositories import (
    MedicationHistoryCategoryCatalogRepository,
)
from app.domain.medication_history.value_objects import (
    MajorCategoryDefinition,
    MediumCategoryDefinition,
)


@dataclass(frozen=True, kw_only=True)
class UpdateCategoryCatalogCommand:
    """法人別薬歴記載区分カタログの更新入力。"""

    corporate_id: str
    major_categories: tuple[MajorCategoryInput, ...] = ()
    medium_categories: tuple[MediumCategoryInput, ...] = ()


class UpdateCategoryCatalogUseCase:
    """法人の薬歴記載区分カタログを更新するユースケース。"""

    def __init__(
        self,
        repository: MedicationHistoryCategoryCatalogRepository,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access

    async def execute(
        self, command: UpdateCategoryCatalogCommand
    ) -> CategoryCatalogDto:
        """区分カタログを更新する。"""
        parsed_corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=parsed_corporate_id,
            permission=Permission.MANAGE_MEDICATION_HISTORY,
        )
        existing = await self._repository.get(corporate_id=parsed_corporate_id)
        catalog_id = (
            existing.id if existing is not None else CategoryCatalogId.generate()
        )
        major_categories = tuple(
            MajorCategoryDefinition(
                code=MajorCategoryCode(m.code),
                name=MajorCategoryName(m.name),
                display_order=CategoryDisplayOrder(m.display_order),
                is_enabled=m.is_enabled,
            )
            for m in command.major_categories
        )
        medium_categories = tuple(
            MediumCategoryDefinition(
                code=MediumCategoryCode(m.code),
                major_category_code=MajorCategoryCode(m.major_category_code),
                name=MediumCategoryName(m.name),
                display_order=CategoryDisplayOrder(m.display_order),
                is_required=m.is_required,
                is_enabled=m.is_enabled,
            )
            for m in command.medium_categories
        )
        catalog = MedicationHistoryCategoryCatalog(
            id=catalog_id,
            corporate_id=parsed_corporate_id,
            major_categories=major_categories,
            medium_categories=medium_categories,
        )
        await self._repository.save(catalog)
        return CategoryCatalogDto.from_entity(catalog)
