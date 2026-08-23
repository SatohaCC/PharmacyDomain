"""データクラスの宣言型と実際のフィールド値を照合する共通ガード。"""

from __future__ import annotations

import inspect
import types
from collections.abc import Mapping
from dataclasses import fields
from datetime import date, datetime
from typing import Any, TypeVar, Union, cast, get_args, get_origin

from app.base.domain.exceptions import DomainValidationError


def _declared_field_types(cls: type[Any]) -> tuple[tuple[str, object], ...]:
    """具象クラスから見て最も近い宣言元のフィールド型を解決する。"""
    declared: list[tuple[str, object]] = []
    for field in fields(cls):
        for owner in cls.__mro__:
            annotations = inspect.get_annotations(owner, eval_str=False)
            if field.name not in annotations:
                continue
            try:
                annotation = inspect.get_annotations(owner, eval_str=True)[field.name]
            except (NameError, TypeError) as exc:
                raise RuntimeError(
                    f"{owner.__qualname__}.{field.name} の型注釈を解決できません。"
                ) from exc
            _ensure_resolved(annotation, owner=owner, field_name=field.name)
            declared.append((field.name, annotation))
            break
        else:
            raise RuntimeError(
                f"{cls.__qualname__}.{field.name} の型注釈が見つかりません。"
            )
    return tuple(declared)


def _ensure_resolved(
    annotation: object,
    *,
    owner: type[object],
    field_name: str,
) -> None:
    """未解決の型変数を黙って許可せず、設定誤りとして明示する。"""
    if isinstance(annotation, TypeVar):
        raise RuntimeError(
            f"{owner.__qualname__}.{field_name} に未解決の型変数があります。"
        )
    for argument in get_args(annotation):
        _ensure_resolved(argument, owner=owner, field_name=field_name)


def _matches_declared_type(value: object, annotation: object) -> bool:
    """このプロジェクトのドメインフィールドで使う型構造を照合する。"""
    if annotation is Any:
        return True
    if annotation is None or annotation is types.NoneType:
        return value is None

    origin = get_origin(annotation)
    arguments = get_args(annotation)
    if origin in (types.UnionType, Union):
        return any(_matches_declared_type(value, item) for item in arguments)
    if origin is tuple:
        if not isinstance(value, tuple):
            return False
        if len(arguments) == 2 and arguments[1] is Ellipsis:
            return all(_matches_declared_type(item, arguments[0]) for item in value)
        return len(value) == len(arguments) and all(
            _matches_declared_type(item, expected)
            for item, expected in zip(value, arguments, strict=True)
        )
    if origin is frozenset:
        return isinstance(value, frozenset) and all(
            _matches_declared_type(item, arguments[0]) for item in value
        )

    if annotation is date:
        return type(value) is date
    if annotation is datetime:
        return isinstance(value, datetime)
    if annotation is int:
        return type(value) is int
    if annotation is float:
        return type(value) is float
    if isinstance(annotation, type):
        return isinstance(value, annotation)

    raise RuntimeError(f"型ガードが未対応の型注釈です: {annotation!r}")


def _expected_type_name(annotation: object) -> str:
    """検証エラーへ表示する宣言型名を組み立てる。"""
    if annotation is None or annotation is types.NoneType:
        return "None"
    origin = get_origin(annotation)
    arguments = get_args(annotation)
    if origin in (types.UnionType, Union):
        return " または ".join(_expected_type_name(item) for item in arguments)
    if origin is tuple:
        if len(arguments) == 2 and arguments[1] is Ellipsis:
            return f"tuple[{_expected_type_name(arguments[0])}, ...]"
        return f"tuple[{', '.join(_expected_type_name(item) for item in arguments)}]"
    if origin is frozenset:
        return f"frozenset[{_expected_type_name(arguments[0])}]"
    return getattr(annotation, "__name__", repr(annotation))


def ensure_declared_field_types(
    instance: object,
    *,
    labels: Mapping[str, str] | None = None,
) -> None:
    """全フィールドが宣言型に適合することを検証する。"""
    field_labels = labels or {}
    instance_type = cast(type[Any], type(instance))
    for field_name, annotation in _declared_field_types(instance_type):
        value = getattr(instance, field_name)
        if _matches_declared_type(value, annotation):
            continue
        label = field_labels.get(field_name, field_name)
        expected = _expected_type_name(annotation)
        raise DomainValidationError(f"{label}は {expected} で指定してください。")
