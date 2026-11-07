"""受付の今回記載欄入力値DTO。"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.reception.value_objects import CurrentRecordFieldValue


@dataclass(frozen=True, kw_only=True)
class CurrentRecordFieldValueDto:
    """受付に紐づく今回記載欄の入力値DTO。"""

    field_id: str
    value_text: str

    @classmethod
    def from_value(cls, value: CurrentRecordFieldValue) -> CurrentRecordFieldValueDto:
        return cls(
            field_id=str(value.field_id.value),
            value_text=value.value_text.value,
        )


__all__ = ["CurrentRecordFieldValueDto"]
