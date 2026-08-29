"""`is_active` を持てるクラスを表で固定する。

``tests/domain/test_lifecycle_dialects.py`` は **集約ルート** の無効化方言を守るが、
子の Value Object に ``is_active`` を足しても検出できない。
以前はこの制約をレビュー任せにしていたが、レビューは仕組みではない。

危ないのは**期間を持つ子レコードに真偽フラグを足すこと**である。
``ConcurrentMedicationRecord`` は ``ended_on`` で継続中かどうかが決まるので、
``is_active`` を足すと同じ事実の表現が2つになり、必ず食い違う。

ここでは ``app/domain`` と ``app/base/domain`` の全 dataclass を走査し、
``is_active`` を持つクラスの集合が下の表と一致することを要求する。
"""

from __future__ import annotations

import dataclasses
import importlib
import pkgutil
from typing import Any

import app.base.domain
import app.domain

#: ``is_active`` フィールドを持ってよいクラスと、その理由。
#:
#: 集約ルートの ``active_flag`` 方言（``LIFECYCLE_DIALECTS``）に対応する。
#: 期間（``*_on`` / ``*_date``）から導出できる子レコードをここへ足してはならない。
ALLOWED_ACTIVE_FLAG_OWNERS: dict[str, str] = {
    "Staff": "集約ルート。無効化方言は active_flag（スタッフコードの再利用は不可）",
    "PatientExternalIdentifier": (
        "集約ルート。無効化方言は active_flag（外部IDは無効化後に再利用可）"
    ),
}


def _iter_domain_classes() -> list[Any]:
    """``app/domain`` と ``app/base/domain`` 配下の dataclass を列挙する。

    ``dataclasses.fields()`` は ``DataclassInstance`` 型を要求するが、走査時点では
    静的に絞り込めないため戻り値は ``Any`` にする。
    """
    found: list[Any] = []
    for package in (app.domain, app.base.domain):
        for module_info in pkgutil.walk_packages(
            package.__path__, prefix=f"{package.__name__}."
        ):
            module = importlib.import_module(module_info.name)
            for value in vars(module).values():
                if not isinstance(value, type):
                    continue
                if value.__module__ != module_info.name:
                    continue
                if dataclasses.is_dataclass(value):
                    found.append(value)
    return found


def test_走査対象のクラスが_十分な数見つかる() -> None:
    """走査が壊れると、この検査全体が空振りする。"""
    # Arrange / Act
    actual = _iter_domain_classes()

    # Assert
    assert len(actual) > 50


def test_is_activeを持つクラスが_表と完全一致する() -> None:
    """期間から導出できる子レコードへ ``is_active`` を足すと、ここで落ちる。"""
    # Arrange / Act
    actual = {
        klass.__name__
        for klass in _iter_domain_classes()
        if any(item.name == "is_active" for item in dataclasses.fields(klass))
    }

    # Assert
    assert actual == set(ALLOWED_ACTIVE_FLAG_OWNERS)


def test_併用薬は_期間から継続中かを判定する() -> None:
    """``ConcurrentMedicationRecord`` に真偽フラグが無いことを名指しで固定する。

    表との一致だけだと、表の側を編集して通してしまえる。この向きも1本残す。
    """
    # Arrange
    from app.domain.medication_history.value_objects import (
        ConcurrentMedicationRecord,
    )

    # Act
    field_names = {item.name for item in dataclasses.fields(ConcurrentMedicationRecord)}

    # Assert
    assert "is_active" not in field_names
    assert "ended_on" in field_names
    assert hasattr(ConcurrentMedicationRecord, "is_active_on")
