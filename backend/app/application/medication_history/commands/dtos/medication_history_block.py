"""薬歴ブロックのDTO定義。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.application.common.optional_conversion import unwrap
from app.domain.medication_history.entities import MedicationHistoryBlock


@dataclass(frozen=True, kw_only=True)
class MedicationHistoryBlockDto:
    """薬歴ブロックの表示用DTO。"""

    id: str
    category_code: str
    category_name: str
    category_badge_label: str
    content: str
    display_order: int
    source_module: str
    source_id: str | None = None
    updated_by: str | None = None
    updated_by_name: str = ""
    updated_at: datetime | None = None

    @classmethod
    def from_domain(
        cls,
        block: MedicationHistoryBlock,
        *,
        category_name: str = "",
        category_badge_label: str = "",
        updated_by_name: str = "",
    ) -> MedicationHistoryBlockDto:
        """DomainモデルからDTOを生成する。"""
        cat_name = category_name or block.category_code.value
        badge_label = category_badge_label or cat_name
        return cls(
            id=str(block.id.value),
            category_code=block.category_code.value,
            category_name=cat_name,
            category_badge_label=badge_label,
            content=block.content.value,
            display_order=block.display_order.value,
            source_module=block.source_module.value,
            source_id=unwrap(block.source_id),
            updated_by=str(block.updated_by.value)
            if block.updated_by is not None
            else None,
            updated_by_name=updated_by_name,
            updated_at=block.updated_at,
        )
