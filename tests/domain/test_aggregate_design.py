"""集約設計規則（ID参照、境界、不変条件保護）を強制するアーキテクチャテスト。

AGENTS.md「テナント境界: 集約間は ID 参照のみ（他集約のエンティティを直接保持しない）」
およびDDDの集約設計原則を実行可能にする。
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
import typing
from typing import Any, get_args

import app.domain
from app.domain.foundation.entity import AggregateRoot, Entity
from app.domain.foundation.primitives.base import DomainPrimitive

#: 承認された全具象集約ルートの一覧（12コンテキスト・19集約）。
EXPECTED_AGGREGATE_ROOTS: frozenset[str] = frozenset(
    {
        "Corporate",
        "CoverageSelectionRecord",
        "DispensingProcess",
        "MedicationHistoryCategoryCatalog",
        "MedicationHistoryRecord",
        "Medicine",
        "Patient",
        "PatientCoverage",
        "PatientExternalIdentifier",
        "PatientMedicalProfile",
        "Prescription",
        "Staff",
        "StaffPersonLink",
        "Store",
        "StoreManagerAssignment",
        "AccountPerson",
        "UserAccount",
        "CorporateMembership",
        "UserInvitation",
    }
)

#: 集約ルートが自集約の内部構成要素として保持することを許可された子エンティティ。
ALLOWED_CHILD_ENTITIES: dict[str, frozenset[str]] = {
    "Prescription": frozenset({"PrescriptionInquiry"}),
    "MedicationHistoryRecord": frozenset({"TracingReport", "FollowUpRecord"}),
}


def _import_all_domain_modules() -> None:
    """app.domain 配下の全モジュールを走査してロードする。"""
    for module_info in pkgutil.walk_packages(
        app.domain.__path__, prefix=f"{app.domain.__name__}."
    ):
        importlib.import_module(module_info.name)


def _all_concrete_aggregate_roots() -> list[type[object]]:
    """app.domain 配下の具象集約ルートクラスを列挙する。"""
    _import_all_domain_modules()

    def descend(cls: type[object]) -> list[type[object]]:
        found: list[type[object]] = []
        for subclass in cls.__subclasses__():
            found.append(subclass)
            found.extend(descend(subclass))
        return found

    return sorted(
        [
            cls
            for cls in dict.fromkeys(descend(AggregateRoot))
            if not inspect.isabstract(cls) and cls.__module__.startswith("app.domain.")
        ],
        key=lambda c: c.__name__,
    )


def _extract_referenced_entity_types(annotation: Any) -> set[type[object]]:
    """型注釈から含まれる Entity 型（DomainPrimitiveを除く）を抽出する。"""
    found: set[type[object]] = set()

    if (
        isinstance(annotation, type)
        and issubclass(annotation, Entity)
        and not issubclass(annotation, DomainPrimitive)
    ):
        found.add(annotation)

    for arg in get_args(annotation):
        found.update(_extract_referenced_entity_types(arg))

    return found


def test_全集約ルートが網羅的に検出される() -> None:
    """TC-01: 定義されている全19集約ルートが漏れなく検出され、許可表と一致する。"""
    roots = _all_concrete_aggregate_roots()
    actual_names = {cls.__name__ for cls in roots}

    assert actual_names == EXPECTED_AGGREGATE_ROOTS, (
        f"集約ルートの一覧が想定と異なります。\n"
        f"余剰: {actual_names - EXPECTED_AGGREGATE_ROOTS}\n"
        f"不足: {EXPECTED_AGGREGATE_ROOTS - actual_names}"
    )


def test_集約ルートは他集約をIDのみで参照する() -> None:
    """TC-02: 他集約のエンティティインスタンスを直接フィールドとして保持しない（ID参照のみ）。"""
    roots = _all_concrete_aggregate_roots()
    violations: list[str] = []

    for root in roots:
        allowed_children = ALLOWED_CHILD_ENTITIES.get(root.__name__, frozenset())
        hints = typing.get_type_hints(root)

        for field_name, annotation in hints.items():
            # 自身のIDフィールドはスキップ
            if field_name == "id":
                continue

            referenced_entities = _extract_referenced_entity_types(annotation)
            for entity_cls in referenced_entities:
                if entity_cls.__name__ not in allowed_children:
                    violations.append(
                        f"{root.__name__}.{field_name} -> {entity_cls.__name__} "
                        f"（許可された子エンティティではありません。ID参照にしてください）"
                    )

    assert not violations, (
        "集約間の直接エンティティ参照違反が見つかりました:\n" + "\n".join(violations)
    )


def test_集約ルートのdataclass宣言規則が統一されている() -> None:
    """TC-03: 全集約ルートが @dataclass(frozen=True, eq=False, kw_only=True) である。"""
    roots = _all_concrete_aggregate_roots()
    violations: list[str] = []

    for root in roots:
        params = getattr(root, "__dataclass_params__", None)
        if not params:
            violations.append(f"{root.__name__}: @dataclass ではありません")
            continue

        if not params.frozen:
            violations.append(f"{root.__name__}: frozen=True ではありません")
        if params.eq:
            violations.append(
                f"{root.__name__}: eq=False ではありません（EntityのID同一性を壊します）"
            )
        if not params.kw_only:
            violations.append(f"{root.__name__}: kw_only=True ではありません")

    assert not violations, (
        "集約ルートの dataclass 宣言規則違反が見つかりました:\n" + "\n".join(violations)
    )


def test_集約ルートのIDはDomainPrimitiveである() -> None:
    """TC-04: 全集約ルートの id フィールドが DomainPrimitive を継承している。"""
    roots = _all_concrete_aggregate_roots()
    violations: list[str] = []

    for root in roots:
        hints = typing.get_type_hints(root)
        if "id" not in hints:
            violations.append(f"{root.__name__}: 'id' フィールドがありません")
            continue

        id_type = hints["id"]
        if not (isinstance(id_type, type) and issubclass(id_type, DomainPrimitive)):
            violations.append(
                f"{root.__name__}.id の型 {id_type} は DomainPrimitive ではありません"
            )

    assert not violations, "集約ルートの ID 型定義違反が見つかりました:\n" + "\n".join(
        violations
    )


def test_集約ルートはvalidateフックを持つ() -> None:
    """TC-05: 全集約ルートが validate() メソッドを実装している。"""
    roots = _all_concrete_aggregate_roots()
    violations: list[str] = []

    for root in roots:
        if not hasattr(root, "validate") or not callable(root.validate):
            violations.append(
                f"{root.__name__}: validate() メソッドが実装されていません"
            )

    assert not violations, (
        "validate() を持たない集約ルートが見つかりました:\n" + "\n".join(violations)
    )


def test_集約内子エンティティの構成が許可表と一致する() -> None:
    """TC-06: 集約ルートが保持する子エンティティが許可表と完全一致する。"""
    roots = _all_concrete_aggregate_roots()
    actual_child_entities: dict[str, set[str]] = {}

    for root in roots:
        hints = typing.get_type_hints(root)
        children: set[str] = set()

        for field_name, annotation in hints.items():
            if field_name == "id":
                continue
            for entity_cls in _extract_referenced_entity_types(annotation):
                children.add(entity_cls.__name__)

        if children:
            actual_child_entities[root.__name__] = children

    expected_dict = {
        name: set(children) for name, children in ALLOWED_CHILD_ENTITIES.items()
    }
    assert actual_child_entities == expected_dict, (
        f"子エンティティの構成が許可表と異なります:\n"
        f"実測: {actual_child_entities}\n"
        f"期待: {expected_dict}"
    )
