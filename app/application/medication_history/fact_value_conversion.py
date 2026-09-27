"""HTTP の事実訂正値を対象項目の Domain 型へ変換する。"""

from __future__ import annotations

import types
from dataclasses import MISSING, fields, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any, Union, cast, get_args, get_origin, get_type_hints

from app.domain.foundation.primitives.base import DomainPrimitive
from app.domain.medication_history.exceptions import MedicationHistoryDomainError
from app.domain.medication_history.fact_correction import (
    FACT_ARRAY_TYPES,
    FACT_FIELD_TYPES,
)
from app.domain.medication_history.medication_history_record import (
    MedicationHistoryRecord,
)
from app.domain.staff.primitives import StaffId


def convert_fact_value(
    record: MedicationHistoryRecord, *, target: str, raw: object
) -> object:
    """対象フィールドの宣言型を使って入力値を構築する。"""
    field_name = target
    if target not in FACT_FIELD_TYPES and target not in FACT_ARRAY_TYPES:
        field_name = next(
            (
                name
                for name in FACT_ARRAY_TYPES
                if any(item.id == target for item in record.fact_elements(name))
            ),
            "",
        )
    expected = FACT_FIELD_TYPES.get(field_name) or FACT_ARRAY_TYPES.get(field_name)
    if expected is None:
        raise MedicationHistoryDomainError("訂正対象がありません。")
    if raw is None:
        return None
    return _convert(raw, expected)


def _convert(raw: object, annotation: object) -> object:
    """注釈に沿って辞書・配列・スカラを Domain 値に変換する。"""
    origin = get_origin(annotation)
    if origin in (Union, types.UnionType):
        if raw is None and type(None) in get_args(annotation):
            return None
        for choice in get_args(annotation):
            if choice is type(None):
                continue
            try:
                return _convert(raw, choice)
            except MedicationHistoryDomainError, TypeError, ValueError:
                continue
        raise MedicationHistoryDomainError("訂正値の型が正しくありません。")
    if origin in (tuple, list):
        if not isinstance(raw, (tuple, list)):
            raise MedicationHistoryDomainError("配列の訂正値が正しくありません。")
        element_type = get_args(annotation)[0]
        return tuple(_convert(item, element_type) for item in raw)
    if not isinstance(annotation, type):
        raise MedicationHistoryDomainError("訂正値の型が正しくありません。")
    if annotation is bool:
        if type(raw) is not bool:
            raise MedicationHistoryDomainError("真偽値を指定してください。")
        return raw
    if annotation is int:
        if type(raw) is not int:
            raise MedicationHistoryDomainError("整数を指定してください。")
        return raw
    if isinstance(raw, annotation):
        return raw
    if annotation is str:
        if not isinstance(raw, str):
            raise MedicationHistoryDomainError("文字列を指定してください。")
        return raw
    if annotation is date:
        if not isinstance(raw, str):
            raise MedicationHistoryDomainError("日付の形式が正しくありません。")
        try:
            return date.fromisoformat(raw)
        except ValueError as error:
            raise MedicationHistoryDomainError(
                "日付の形式が正しくありません。"
            ) from error
    if annotation is datetime:
        if not isinstance(raw, str):
            raise MedicationHistoryDomainError("日時の形式が正しくありません。")
        try:
            return datetime.fromisoformat(raw)
        except ValueError as error:
            raise MedicationHistoryDomainError(
                "日時の形式が正しくありません。"
            ) from error
    if issubclass(annotation, Enum):
        try:
            return annotation(raw)
        except ValueError as error:
            raise MedicationHistoryDomainError("列挙値が正しくありません。") from error
    if issubclass(annotation, DomainPrimitive):
        try:
            if annotation is StaffId:
                if not isinstance(raw, str):
                    raise MedicationHistoryDomainError("スタッフIDが正しくありません。")
                return StaffId.parse(raw)
            if annotation.__name__.endswith("Timestamp"):
                raw = _convert(raw, datetime)
            return annotation(raw)
        except (TypeError, ValueError) as error:
            raise MedicationHistoryDomainError(
                "訂正値の形式が正しくありません。"
            ) from error
    if is_dataclass(annotation):
        if not isinstance(raw, dict):
            raise MedicationHistoryDomainError("訂正値は項目を持つ必要があります。")
        hints = get_type_hints(annotation)
        names = {item.name for item in fields(annotation)}
        if set(raw) - names:
            raise MedicationHistoryDomainError("訂正値に未知の項目があります。")
        kwargs: dict[str, object] = {}
        for item in fields(annotation):
            if item.name in raw:
                kwargs[item.name] = _convert(raw[item.name], hints[item.name])
            elif item.default is MISSING and item.default_factory is MISSING:
                raise MedicationHistoryDomainError("訂正値の必須項目がありません。")
        return cast(Any, annotation)(**kwargs)
    raise MedicationHistoryDomainError("訂正値の型が正しくありません。")
