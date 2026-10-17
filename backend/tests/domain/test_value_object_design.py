"""DDD Value Object および DomainPrimitive の設計規則・粒度を強制するアーキテクチャテスト。

Value Object の不変性（frozen, kw_only）、可変型排除、Entity非保持、同一性不在、
ならびに Entity / AggregateRoot における Primitive Obsession（基本型露出）の抑止を機械的に検証する。
"""

from __future__ import annotations

import dataclasses
import decimal
import importlib
import inspect
import pkgutil
import typing
from typing import Any

import app.domain
from app.domain.foundation.entity import Entity
from app.domain.foundation.primitives.base import DomainPrimitive
from app.domain.foundation.value_object import ValueObject

_BARE_PRIMITIVE_TYPES = (str, int, float, decimal.Decimal)
_MUTABLE_CONTAINER_ORIGINS = (list, dict, set)


def _import_all_domain_modules() -> None:
    """app.domain 配下の全モジュールを走査してロードする。"""
    for module_info in pkgutil.walk_packages(
        app.domain.__path__, prefix=f"{app.domain.__name__}."
    ):
        importlib.import_module(module_info.name)


def _get_all_subclasses(cls: type[object]) -> list[type[object]]:
    """再帰的に全サブクラスを取得する。"""
    subclasses: list[type[object]] = []
    for subclass in cls.__subclasses__():
        subclasses.append(subclass)
        subclasses.extend(_get_all_subclasses(subclass))
    return subclasses


def _all_concrete_value_objects() -> list[type[object]]:
    """app.domain 配下の具象 ValueObject クラスを列挙する。"""
    _import_all_domain_modules()
    return sorted(
        [
            cls
            for cls in dict.fromkeys(_get_all_subclasses(ValueObject))
            if not inspect.isabstract(cls) and cls.__module__.startswith("app.domain.")
        ],
        key=lambda c: c.__name__,
    )


def _all_concrete_domain_primitives() -> list[type[object]]:
    """app.domain 配下の具象 DomainPrimitive クラスを列挙する。"""
    _import_all_domain_modules()
    return sorted(
        [
            cls
            for cls in dict.fromkeys(_get_all_subclasses(DomainPrimitive))
            if not inspect.isabstract(cls) and cls.__module__.startswith("app.domain.")
        ],
        key=lambda c: c.__name__,
    )


def _all_concrete_entities() -> list[type[object]]:
    """app.domain 配下の具象 Entity / AggregateRoot クラスを列挙する。"""
    _import_all_domain_modules()
    return sorted(
        [
            cls
            for cls in dict.fromkeys(_get_all_subclasses(Entity))
            if not inspect.isabstract(cls)
            and not issubclass(cls, DomainPrimitive)
            and cls.__module__.startswith("app.domain.")
        ],
        key=lambda c: c.__name__,
    )


def _contains_entity_type(annotation: Any) -> bool:
    """型注釈が Entity（DomainPrimitiveを除く）を参照しているかを判定する。"""
    if (
        isinstance(annotation, type)
        and issubclass(annotation, Entity)
        and not issubclass(annotation, DomainPrimitive)
    ):
        return True

    return any(_contains_entity_type(arg) for arg in typing.get_args(annotation))


def _contains_mutable_container(annotation: Any) -> bool:
    """型注釈が可変コレクション（list, dict, set）を参照しているかを判定する。"""
    origin = typing.get_origin(annotation)
    if origin in _MUTABLE_CONTAINER_ORIGINS:
        return True

    return any(_contains_mutable_container(arg) for arg in typing.get_args(annotation))


def _contains_bare_primitive(annotation: Any) -> bool:
    """型注釈が生の基本型（str, int, float, Decimal）を参照しているかを判定する。"""
    if annotation in _BARE_PRIMITIVE_TYPES:
        return True

    return any(_contains_bare_primitive(arg) for arg in typing.get_args(annotation))


def test_全ValueObjectがfrozenかつkw_onlyである() -> None:
    """TC-01: 全ValueObjectが @dataclass(frozen=True, kw_only=True) で宣言されていること。"""
    vos = _all_concrete_value_objects()
    assert len(vos) >= 100, f"検出されたValueObject数が想定外に少なすぎます: {len(vos)}"

    violations: list[str] = []
    for vo in vos:
        params = getattr(vo, "__dataclass_params__", None)
        if not params:
            violations.append(f"{vo.__name__}: @dataclass ではありません")
            continue
        if not params.frozen:
            violations.append(
                f"{vo.__name__}: frozen=True ではありません（不変性を破ります）"
            )
        if not params.kw_only:
            violations.append(
                f"{vo.__name__}: kw_only=True ではありません（同型引数の取り違え防止を欠きます）"
            )

    assert not violations, (
        "ValueObject の dataclass 宣言規則違反が見つかりました:\n"
        + "\n".join(violations)
    )


def test_全ValueObjectが可変コレクションを持たない() -> None:
    """TC-02: 全ValueObjectのフィールドに list, dict, set が含まれず、tuple / frozenset のみであること。"""
    vos = _all_concrete_value_objects()
    violations: list[str] = []

    for vo in vos:
        hints = typing.get_type_hints(vo)
        for fname, ftype in hints.items():
            if fname.startswith("_"):
                continue
            if _contains_mutable_container(ftype):
                violations.append(
                    f"{vo.__name__}.{fname} ({ftype}): 可変コレクション型です。tuple や frozenset を使用してください"
                )

    assert not violations, (
        "ValueObject の可変コレクション型参照が見つかりました:\n"
        + "\n".join(violations)
    )


def test_全ValueObjectがEntityを直接参照しない() -> None:
    """TC-03: 全ValueObjectのフィールドに Entity（AggregateRoot含む）の直接参照が存在しないこと。"""
    vos = _all_concrete_value_objects()
    violations: list[str] = []

    for vo in vos:
        hints = typing.get_type_hints(vo)
        for fname, ftype in hints.items():
            if fname.startswith("_"):
                continue
            if _contains_entity_type(ftype):
                violations.append(
                    f"{vo.__name__}.{fname} ({ftype}): Entityを直接保持しています。ID参照または値オブジェクトにしてください"
                )

    assert not violations, (
        "ValueObject による Entity 直接参照違反が見つかりました:\n"
        + "\n".join(violations)
    )


def test_全ValueObjectがidフィールドを持たない() -> None:
    """TC-04: 全ValueObjectが自前の id フィールドを持たず、純粋な値として等価性を持つこと。"""
    vos = _all_concrete_value_objects()
    violations: list[str] = []

    for vo in vos:
        hints = typing.get_type_hints(vo)
        for fname in hints:
            if fname == "id":
                violations.append(
                    f"{vo.__name__} が 'id' フィールドを持っています。同一性（ID）を持つ概念は Entity にすべきです"
                )

    assert not violations, (
        "id フィールドを持つ ValueObject が見つかりました:\n" + "\n".join(violations)
    )


def test_全DomainPrimitiveの宣言規則と整合性() -> None:
    """TC-05: 全DomainPrimitiveが frozen=True、フィールド数1（value）、validate() 実装を満たすこと。"""
    dps = _all_concrete_domain_primitives()
    assert len(dps) >= 170, (
        f"検出されたDomainPrimitive数が想定外に少なすぎます: {len(dps)}"
    )

    violations: list[str] = []
    for dp in dps:
        params = getattr(dp, "__dataclass_params__", None)
        if not params:
            violations.append(f"{dp.__name__}: @dataclass ではありません")
            continue
        if not params.frozen:
            violations.append(f"{dp.__name__}: frozen=True ではありません")

        fields = dataclasses.fields(dp)  # type: ignore[arg-type]
        if len(fields) != 1:
            violations.append(
                f"{dp.__name__}: フィールド数が1個ではありません（{len(fields)}個: {[f.name for f in fields]}）"
            )
        elif fields[0].name != "value":
            violations.append(
                f"{dp.__name__}: フィールド名が 'value' ではありません（'{fields[0].name}'）"
            )

        if not hasattr(dp, "validate") or not callable(dp.validate):
            violations.append(f"{dp.__name__}: validate() メソッドが実装されていません")

    assert not violations, (
        "DomainPrimitive の宣言規則違反が見つかりました:\n" + "\n".join(violations)
    )


def test_全EntityがPrimitiveObsessionを持たない() -> None:
    """TC-06: 全Entity / AggregateRootのフィールドに生の基本型（str, int, float, Decimal）が露出していないこと。"""
    entities = _all_concrete_entities()
    assert len(entities) >= 20, (
        f"検出されたEntity数が想定外に少なすぎます: {len(entities)}"
    )

    violations: list[str] = []
    for entity in entities:
        hints = typing.get_type_hints(entity)
        for fname, ftype in hints.items():
            if fname.startswith("_"):
                continue
            if _contains_bare_primitive(ftype):
                violations.append(
                    f"{entity.__name__}.{fname} ({ftype}): 生の基本型（Primitive Obsession）です。"
                    "DomainPrimitive または ValueObject でラップしてください"
                )

    assert not violations, (
        "Entity の Primitive Obsession（基本型露出）が見つかりました:\n"
        + "\n".join(violations)
    )
