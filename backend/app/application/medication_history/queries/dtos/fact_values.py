"""Applicationのget_medication_historyを定義する。"""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from datetime import date, datetime
from enum import Enum
from uuid import UUID

from app.application.common.optional_conversion import unwrap
from app.domain.foundation.primitives.base import DomainPrimitive
from app.domain.medication_history.entities import FactElement, MedicationHistoryRecord
from app.domain.medication_history.value_objects import (
    FACT_ARRAY_TYPES,
    ProfileUpdateIntents,
)


def _fact_json(value: object) -> object:
    """薬歴の監査事実をAPIで読める構造へ変換する。"""
    if isinstance(value, DomainPrimitive):
        return _fact_json(value.value)
    if isinstance(value, Enum):
        return _fact_json(value.value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if is_dataclass(value) and (not isinstance(value, type)):
        return {
            item.name: _fact_json(getattr(value, item.name)) for item in fields(value)
        }
    if isinstance(value, tuple | list):
        return [_fact_json(item) for item in value]
    return value


def _element_json(element: FactElement) -> dict[str, object]:
    """配列要素IDと値の項目を1つの表示単位にする。"""
    payload = _fact_json(element.value)
    if isinstance(payload, dict):
        return {"id": element.id.value, **payload}
    return {"id": element.id.value, "value": payload}


def _profile_updates_json(
    record: MedicationHistoryRecord, *, original: bool
) -> dict[str, object]:
    """原本または有効な頭書き差分を要素IDつきで返す。"""
    updates = (
        record.profile_updates if original else record.effective_facts.profile_updates
    )
    result: dict[str, object] = {}
    for item in fields(ProfileUpdateIntents):
        field_name = f"profile_updates.{item.name}"
        if field_name in FACT_ARRAY_TYPES:
            elements = (
                record.original_fact_elements(field_name)
                if original
                else record.fact_elements(field_name)
            )
            result[item.name] = [_element_json(element) for element in elements]
        else:
            result[item.name] = _fact_json(getattr(updates, item.name))
    return result


def _original_facts_json(record: MedicationHistoryRecord) -> dict[str, object]:
    """交付時の記録値を訂正後の表示と独立して返す。"""
    return {
        "counselor_id": _fact_json(record.counselor_id),
        "counseled_at": _fact_json(record.counseled_at),
        "method": _fact_json(record.method),
        "handbook_status": _fact_json(record.handbook_status),
        "residual_drug": _fact_json(record.residual_drug),
        "information_sheet_provided": record.information_sheet_provided,
        "profile_updates": _profile_updates_json(record, original=True),
        "additional_notes": [
            _element_json(item)
            for item in record.original_fact_elements("additional_notes")
        ],
        "billing_additions": [
            _element_json(item)
            for item in record.original_fact_elements("billing_additions")
        ],
        "source_system": _fact_json(record.source_system),
        "delay_reason": _fact_json(record.delay_reason),
        "review_result": _fact_json(record.review_result),
    }


def _fact_corrections_json(
    record: MedicationHistoryRecord,
) -> tuple[dict[str, object], ...]:
    """追記順を保った監査履歴を返す。"""
    return tuple(
        {
            "id": item.id.value,
            "target": item.target.value,
            "field_name": item.field_name,
            "operation": item.operation,
            "before": _fact_json(item.before),
            "after": _fact_json(item.after),
            "reason": item.reason.value,
            "corrected_by": _fact_json(item.corrected_by),
            "recorded_at": _fact_json(item.recorded_at),
            "element_id": unwrap(item.element_id),
        }
        for item in record.fact_corrections
    )
