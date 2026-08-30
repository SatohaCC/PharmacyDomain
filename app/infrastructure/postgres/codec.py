"""集約 payload の型付き JSON codec。"""

from __future__ import annotations

import types
import uuid
from collections.abc import Callable, Mapping
from dataclasses import MISSING, fields, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import (
    Annotated,
    Any,
    Literal,
    TypeVar,
    Union,
    cast,
    get_args,
    get_origin,
    get_type_hints,
)

from app.domain.foundation.primitives.base import DomainPrimitive


class PersistenceMappingError(ValueError):
    """DB の payload を集約へ復元できない場合の例外。"""


_PrimitiveType = type[DomainPrimitive[object]]

_FieldSpec = tuple[str, object, bool]
"""フィールド名、解決済みの型注釈、既定値を持つか。"""

# 型注釈と型引数はクラス定義後に変わらないので、クラスをキーに使い回す。
# functools.cache は mypy が type[...] を Hashable と見なさないため使わない。
_FIELD_SPEC_CACHE: dict[type[Any], tuple[_FieldSpec, ...]] = {}
_PRIMITIVE_VALUE_TYPE_CACHE: dict[type[Any], type[object]] = {}


def encode_aggregate(value: object) -> dict[str, object]:
    """集約を JSONB へ格納できる辞書へ変換する。"""
    encoded = _encode(value)
    if not isinstance(encoded, dict):
        raise PersistenceMappingError(
            "集約 payload のルートはオブジェクトである必要があります。"
        )
    return encoded


def decode_aggregate(
    payload: Mapping[str, object], aggregate_type: type[_AggregateT]
) -> _AggregateT:
    """指定された集約型として payload を検証しながら復元する。"""
    decoded = _decode(payload, aggregate_type, context=aggregate_type.__name__)
    if not isinstance(decoded, aggregate_type):
        raise PersistenceMappingError(
            f"payload は {aggregate_type.__name__} として復元できません。"
        )
    return decoded


_AggregateT = TypeVar("_AggregateT")


def _encode(value: object) -> object:
    if isinstance(value, DomainPrimitive):
        return _encode(value.value)
    if isinstance(value, Enum):
        return _encode(value.value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Decimal):
        return str(value)
    if is_dataclass(value):
        return {
            field.name: _encode(getattr(value, field.name)) for field in fields(value)
        }
    if isinstance(value, Mapping):
        encoded_mapping: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise PersistenceMappingError(
                    "JSONB の辞書キーは文字列である必要があります。"
                )
            encoded_mapping[key] = _encode(item)
        return encoded_mapping
    if isinstance(value, (tuple, list, set, frozenset)):
        return [_encode(item) for item in value]
    raise PersistenceMappingError(
        f"JSONBへ変換できない型です: {type(value).__module__}.{type(value).__qualname__}。"
    )


def _decode(value: object, annotation: object, *, context: str) -> object:
    origin = get_origin(annotation)

    if origin is Annotated:
        annotation = get_args(annotation)[0]
        origin = get_origin(annotation)

    if origin in (Union, types.UnionType):
        return _decode_union(value, get_args(annotation), context=context)

    if origin is Literal:
        choices = get_args(annotation)
        if value not in choices:
            raise PersistenceMappingError(f"{context} は許可された値ではありません。")
        return value

    if origin in (tuple, list, set, frozenset):
        return _decode_collection(value, origin, get_args(annotation), context=context)

    if origin in (dict, Mapping):
        return _decode_mapping(value, get_args(annotation), context=context)

    if annotation is Any or annotation is object:
        return value

    if isinstance(annotation, TypeVar):
        return value

    if value is None:
        raise PersistenceMappingError(f"{context} は null にできません。")

    if not isinstance(annotation, type):
        raise PersistenceMappingError(
            f"{context} の型を解決できません: {annotation!r}。"
        )

    if issubclass(annotation, DomainPrimitive):
        return _decode_primitive(
            value, cast(_PrimitiveType, annotation), context=context
        )
    if issubclass(annotation, Enum):
        try:
            return annotation(value)
        except (TypeError, ValueError) as error:
            raise PersistenceMappingError(
                f"{context} の区分値が不正です: {value!r}。"
            ) from error
    if annotation is uuid.UUID:
        return _decode_uuid(value, context=context)
    if annotation is Decimal:
        return _decode_decimal(value, context=context)
    if annotation is datetime:
        return _decode_datetime(value, context=context)
    if annotation is date:
        return _decode_date(value, context=context)
    if annotation in (str, int, float, bool):
        return _decode_scalar(value, annotation, context=context)
    if is_dataclass(annotation):
        return _decode_dataclass(value, annotation, context=context)
    return value


def _decode_union(
    value: object,
    choices: tuple[object, ...],
    *,
    context: str,
) -> object:
    if value is None and type(None) in choices:
        return None
    errors: list[PersistenceMappingError] = []
    for choice in choices:
        if choice is type(None):
            continue
        try:
            return _decode(value, choice, context=context)
        except PersistenceMappingError as error:
            errors.append(error)
    detail = str(errors[-1]) if errors else "候補型がありません。"
    raise PersistenceMappingError(f"{context} の型が不正です: {detail}")


def _decode_collection(
    value: object,
    origin: object,
    arguments: tuple[object, ...],
    *,
    context: str,
) -> object:
    if not isinstance(value, list):
        raise PersistenceMappingError(f"{context} は JSON 配列である必要があります。")
    item_type = arguments[0] if arguments else object
    if origin is tuple and len(arguments) > 1 and arguments[1] is Ellipsis:
        decoded = tuple(
            _decode(item, item_type, context=f"{context}[{index}]")
            for index, item in enumerate(value)
        )
        return decoded
    if origin is tuple and arguments:
        if len(value) != len(arguments):
            raise PersistenceMappingError(f"{context} の要素数が不正です。")
        return tuple(
            _decode(item, item_type, context=f"{context}[{index}]")
            for index, (item, item_type) in enumerate(
                zip(value, arguments, strict=True)
            )
        )
    decoded_items = [
        _decode(item, item_type, context=f"{context}[{index}]")
        for index, item in enumerate(value)
    ]
    if origin is list:
        return decoded_items
    if origin is set:
        return set(decoded_items)
    if origin is frozenset:
        return frozenset(decoded_items)
    return tuple(decoded_items)


def _decode_mapping(
    value: object,
    arguments: tuple[object, ...],
    *,
    context: str,
) -> dict[object, object]:
    if not isinstance(value, dict):
        raise PersistenceMappingError(
            f"{context} は JSON オブジェクトである必要があります。"
        )
    key_type = arguments[0] if arguments else str
    value_type = arguments[1] if len(arguments) > 1 else object
    return {
        _decode(key, key_type, context=f"{context}.key"): _decode(
            item, value_type, context=f"{context}[{key!r}]"
        )
        for key, item in value.items()
    }


def _field_specs(annotation: type[Any]) -> tuple[_FieldSpec, ...]:
    """dataclassのフィールド型注釈を、クラス単位で1度だけ解決する。

    ``from __future__ import annotations`` により ``field.type`` は常に文字列で、
    フィールドごとに評価すると1行の復元でフィールド数ぶんの評価が走る。
    :func:`typing.get_type_hints` は定義元クラスごとの名前空間で解決するため、
    複数モジュールに跨る継承でも正しい型が得られる。
    """
    cached = _FIELD_SPEC_CACHE.get(annotation)
    if cached is not None:
        return cached
    try:
        hints = get_type_hints(annotation, include_extras=True)
    except (NameError, TypeError) as error:
        raise PersistenceMappingError(
            f"{annotation.__qualname__} の型注釈を解決できません。"
        ) from error
    specs: list[_FieldSpec] = []
    for field in fields(annotation):
        if field.name not in hints:
            raise PersistenceMappingError(
                f"{annotation.__qualname__}.{field.name} の型注釈がありません。"
            )
        has_default = (
            field.default is not MISSING or field.default_factory is not MISSING
        )
        specs.append((field.name, hints[field.name], has_default))
    resolved = tuple(specs)
    _FIELD_SPEC_CACHE[annotation] = resolved
    return resolved


def _decode_dataclass(
    value: object, annotation: type[object], *, context: str
) -> object:
    if not isinstance(value, dict):
        raise PersistenceMappingError(
            f"{context} は JSON オブジェクトである必要があります。"
        )
    specs = _field_specs(annotation)
    field_names = {name for name, _, _ in specs}
    unknown = set(value) - field_names
    if unknown:
        names = ", ".join(sorted(unknown))
        raise PersistenceMappingError(
            f"{context} に未知のフィールドがあります: {names}。"
        )
    kwargs: dict[str, object] = {}
    for name, field_annotation, has_default in specs:
        if name not in value:
            if has_default:
                continue
            raise PersistenceMappingError(f"{context}.{name} がありません。")
        kwargs[name] = _decode(
            value[name], field_annotation, context=f"{context}.{name}"
        )
    constructor = cast(Callable[..., object], annotation)
    try:
        return constructor(**kwargs)
    except (TypeError, ValueError) as error:
        raise PersistenceMappingError(f"{context} の構築に失敗しました。") from error


def _primitive_value_type(annotation: type[Any]) -> type[object]:
    """``DomainPrimitive[T]`` の ``T`` を解決する。

    ``BaseNonNegativeDecimal`` のような基底クラスの並びで分岐すると、その並びに
    載らない Primitive が黙って別の型として復元される。型引数そのものを見れば、
    どの Primitive も宣言どおりの型で復元できる。
    """
    cached = _PRIMITIVE_VALUE_TYPE_CACHE.get(annotation)
    if cached is not None:
        return cached
    for klass in annotation.__mro__:
        for base in getattr(klass, "__orig_bases__", ()):
            if get_origin(base) is not DomainPrimitive:
                continue
            argument = get_args(base)[0]
            if isinstance(argument, type):
                _PRIMITIVE_VALUE_TYPE_CACHE[annotation] = argument
                return argument
    raise PersistenceMappingError(
        f"{annotation.__qualname__} の値型を解決できません"
        "（DomainPrimitive[T] の T が型で確定していません）。"
    )


def _decode_primitive(
    value: object,
    annotation: _PrimitiveType,
    *,
    context: str,
) -> DomainPrimitive[object]:
    value_type = _primitive_value_type(annotation)
    raw: object
    if value_type is uuid.UUID:
        raw = _decode_uuid(value, context=context)
    elif value_type is datetime:
        raw = _decode_datetime(value, context=context)
    elif value_type is date:
        raw = _decode_date(value, context=context)
    elif value_type is Decimal:
        raw = _decode_decimal(value, context=context)
    elif value_type in (str, int, bool):
        raw = _decode_scalar(value, value_type, context=context)
    else:
        raise PersistenceMappingError(
            f"{context} の値型 {value_type.__qualname__} は復元できません。"
        )
    try:
        return annotation(raw)
    except (TypeError, ValueError) as error:
        raise PersistenceMappingError(f"{context} の値が不正です。") from error


def _decode_scalar(value: object, annotation: type[object], *, context: str) -> object:
    if annotation is bool:
        valid = isinstance(value, bool)
    elif annotation is int:
        valid = isinstance(value, int) and not isinstance(value, bool)
    else:
        valid = isinstance(value, annotation)
    if not valid:
        raise PersistenceMappingError(f"{context} の型が不正です。")
    return value


def _decode_uuid(value: object, *, context: str) -> uuid.UUID:
    if not isinstance(value, str):
        raise PersistenceMappingError(f"{context} は UUID 文字列である必要があります。")
    try:
        return uuid.UUID(value)
    except ValueError as error:
        raise PersistenceMappingError(f"{context} の UUID が不正です。") from error


def _decode_decimal(value: object, *, context: str) -> Decimal:
    if not isinstance(value, str):
        raise PersistenceMappingError(f"{context} は十進数文字列である必要があります。")
    try:
        return Decimal(value)
    except (ArithmeticError, ValueError) as error:
        raise PersistenceMappingError(f"{context} の十進数が不正です。") from error


def _decode_datetime(value: object, *, context: str) -> datetime:
    if not isinstance(value, str):
        raise PersistenceMappingError(f"{context} は日時文字列である必要があります。")
    try:
        return datetime.fromisoformat(value)
    except ValueError as error:
        raise PersistenceMappingError(f"{context} の日時が不正です。") from error


def _decode_date(value: object, *, context: str) -> date:
    if not isinstance(value, str):
        raise PersistenceMappingError(f"{context} は日付文字列である必要があります。")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise PersistenceMappingError(f"{context} の日付が不正です。") from error
