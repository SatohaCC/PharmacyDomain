"""Applicationのcategory_catalogクエリ用DTOを定義する。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.common.optional_conversion import optional_id, unwrap
from app.domain.medication_history.value_objects import CurrentRecordFieldDefinition


@dataclass(frozen=True, kw_only=True)
class CurrentRecordFieldDto:
    """今回記載欄項目の出力DTO（参照用）。"""

    id: str
    label: str
    display_order: int
    store_id: str | None = None
    category_code: str | None = None
    category_badge_label: str = ""
    is_archived: bool = False

    @classmethod
    def from_value(
        cls,
        value: CurrentRecordFieldDefinition,
        *,
        badge_label: str = "",
    ) -> CurrentRecordFieldDto:
        return cls(
            id=str(value.field_id.value),
            label=value.label.value,
            display_order=value.display_order.value,
            store_id=optional_id(value.store_id),
            category_code=unwrap(value.category_code),
            category_badge_label=badge_label,
            is_archived=value.is_archived,
        )


__all__ = ["CurrentRecordFieldDto"]
