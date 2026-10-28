"""Applicationのcategory_catalogを定義する。"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.medication_history.entities import MedicationHistoryCategoryCatalog
from app.domain.medication_history.value_objects import (
    MajorCategoryDefinition,
    MediumCategoryDefinition,
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
            display_order=value.display_order.value,
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
            display_order=value.display_order.value,
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
