"""法人別薬歴記載区分カタログのApplication層DTOおよびユースケース。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control import CorporateAccessBoundary, Permission
from app.application.medication_history.inputs import UpdateCategoryCatalogCommand
from app.domain.corporate.primitives import CorporateId
from app.domain.medication_history import (
    CategoryCatalogId,
    MajorCategoryCode,
    MajorCategoryDefinition,
    MajorCategoryName,
    MedicationHistoryCategoryCatalog,
    MedicationHistoryCategoryCatalogRepository,
    MediumCategoryCode,
    MediumCategoryDefinition,
    MediumCategoryName,
)


@dataclass(frozen=True, kw_only=True)
class MajorCategoryDto:
    """大区分の出力DTO。"""

    code: str
    name: str
    display_order: int
    is_enabled: bool

    @classmethod
    def from_value(cls, value: MajorCategoryDefinition) -> MajorCategoryDto:
        return cls(
            code=value.code.value,
            name=value.name.value,
            display_order=value.display_order,
            is_enabled=value.is_enabled,
        )


@dataclass(frozen=True, kw_only=True)
class MediumCategoryDto:
    """中区分の出力DTO。"""

    code: str
    major_category_code: str
    name: str
    display_order: int
    is_required: bool
    is_enabled: bool

    @classmethod
    def from_value(cls, value: MediumCategoryDefinition) -> MediumCategoryDto:
        return cls(
            code=value.code.value,
            major_category_code=value.major_category_code.value,
            name=value.name.value,
            display_order=value.display_order,
            is_required=value.is_required,
            is_enabled=value.is_enabled,
        )


@dataclass(frozen=True, kw_only=True)
class CategoryCatalogDto:
    """区分カタログ集約の出力DTO。"""

    id: str
    corporate_id: str
    major_categories: tuple[MajorCategoryDto, ...]
    medium_categories: tuple[MediumCategoryDto, ...]

    @classmethod
    def from_entity(
        cls, entity: MedicationHistoryCategoryCatalog
    ) -> CategoryCatalogDto:
        return cls(
            id=str(entity.id.value),
            corporate_id=str(entity.corporate_id.value),
            major_categories=tuple(
                MajorCategoryDto.from_value(m) for m in entity.major_categories
            ),
            medium_categories=tuple(
                MediumCategoryDto.from_value(m) for m in entity.medium_categories
            ),
        )


class GetCategoryCatalogUseCase:
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
                display_order=m.display_order,
                is_enabled=m.is_enabled,
            )
            for m in command.major_categories
        )
        medium_categories = tuple(
            MediumCategoryDefinition(
                code=MediumCategoryCode(m.code),
                major_category_code=MajorCategoryCode(m.major_category_code),
                name=MediumCategoryName(m.name),
                display_order=m.display_order,
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
