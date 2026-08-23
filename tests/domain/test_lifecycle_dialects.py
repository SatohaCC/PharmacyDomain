"""集約のライフサイクル表現（方言）を凍結するゴールデンテスト。

現在、無効化の表し方は集約ごとに4通りに分かれている。日付つきの
``dated_activation`` が最も表現力が高いが、遡及判定を必要とする到達可能な
UseCase が存在しないため、いま全集約へ広げるのは先回りになる
（AGENTS.md「到達可能なClaim UseCaseがない間はClaim権限を定義しない」と同じ判断）。

そこで「統一しない」という判断そのものを機械で固定する。方言が5つ目に増えても、
新しい集約が増えても、既存集約の方言が変わっても、下の表を編集しない限り
pytest が落ちる。次に集約を足す人の目の前に必ずこの表が出てくる。

既知の限界: 分類はフィールド名と宣言型で行うため、まったく新しい語彙
（例 ``retirement: Retirement``）で既存集約に無効化を実装すると ``none`` と
分類され、表と一致してしまい検出できない。一方、新しい集約は表に行が無いので
必ず落ちる。最大の穴（集約が増えるたびに方言が増える）は塞がっている。
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from dataclasses import fields, is_dataclass
from enum import Enum

import app.domain
from app.base.domain.entity import AggregateRoot

#: 許可するライフサイクル表現。ここを増やすときは okf/ddd/domain.md も更新する。
ALLOWED_DIALECTS = frozenset({"none", "active_flag", "status_enum", "dated_activation"})

#: 集約名 → ライフサイクル方言。実装を変えたらここも変える。
LIFECYCLE_DIALECTS: dict[str, str] = {
    "Corporate": "status_enum",
    "CoverageSelectionRecord": "none",
    "Patient": "none",
    "PatientCoverage": "dated_activation",
    "PatientExternalIdentifier": "active_flag",
    "Staff": "active_flag",
    "Store": "none",
}

#: ``active_flag`` 方言の集約について、無効化後に一意キーを再利用できるか。
#: AGENTS.md はかつて「有効な行に対してだけ一意性を要求する」と全称で書いていたが、
#: Staff はそうなっていない。どちらに倒すかは集約ごとの業務判断なので、
#: 全称命題ではなくこの表で明示し、実挙動は契約テストで固定する。
ACTIVE_FLAG_KEY_REUSE: dict[str, bool] = {
    # 誤った患者へ紐付けた外部IDを無効化してから正しい患者へ付け替えるため、再利用を許す。
    "PatientExternalIdentifier": True,
    # 過去の調剤録・監査の追跡を壊さないため、スタッフコードは再利用させない。
    "Staff": False,
}

_DATED_ACTIVATION_FIELDS = frozenset({"activated_on", "deactivated_on"})


def _import_all_domain_modules() -> None:
    """``AggregateRoot.__subclasses__()`` が全集約を返すよう全モジュールを読み込む。"""
    for module_info in pkgutil.walk_packages(
        app.domain.__path__, prefix=f"{app.domain.__name__}."
    ):
        importlib.import_module(module_info.name)


def _all_aggregate_roots() -> list[type[object]]:
    """``app.domain`` 配下の具象集約ルートを再帰的に集める。"""
    _import_all_domain_modules()

    def descend(cls: type[object]) -> list[type[object]]:
        found: list[type[object]] = []
        for subclass in cls.__subclasses__():
            found.append(subclass)
            found.extend(descend(subclass))
        return found

    return [
        cls
        for cls in dict.fromkeys(descend(AggregateRoot))
        if not inspect.isabstract(cls) and cls.__module__.startswith("app.domain.")
    ]


def _resolved_field_types(cls: type[object]) -> dict[str, object]:
    """宣言元から最も近いフィールド型注釈を解決する（field_guard と同じ方式）。"""
    resolved: dict[str, object] = {}
    for field in fields(cls):  # type: ignore[arg-type]
        for owner in cls.__mro__:
            if field.name not in inspect.get_annotations(owner, eval_str=False):
                continue
            resolved[field.name] = inspect.get_annotations(owner, eval_str=True)[
                field.name
            ]
            break
    return resolved


def _classify(cls: type[object]) -> str:
    """集約のライフサイクル方言を判定する。"""
    found: set[str] = set()
    for name, annotation in _resolved_field_types(cls).items():
        if name == "is_active" and annotation is bool:
            found.add("active_flag")
        elif (
            name == "status"
            and isinstance(annotation, type)
            and issubclass(annotation, Enum)
        ):
            found.add("status_enum")
        elif (
            isinstance(annotation, type)
            and is_dataclass(annotation)
            and {item.name for item in fields(annotation)} >= _DATED_ACTIVATION_FIELDS
        ):
            found.add("dated_activation")
    if len(found) > 1:
        raise AssertionError(
            f"{cls.__name__} が複数のライフサイクル方言を同時に持っています: "
            f"{sorted(found)}。1つに寄せてください。"
        )
    return found.pop() if found else "none"


def test_集約のライフサイクル方言_実装が許可表と完全一致する() -> None:
    # Arrange / Act
    actual = {cls.__name__: _classify(cls) for cls in _all_aggregate_roots()}

    # Assert: 集約の追加・削除・方言変更はすべてここで落ちる
    assert actual == LIFECYCLE_DIALECTS


def test_集約のライフサイクル方言_許可された4方言以外は存在しない() -> None:
    # Arrange / Act
    actual = set(LIFECYCLE_DIALECTS.values())

    # Assert
    assert actual <= ALLOWED_DIALECTS


def test_無効化フラグ方言の集約_一意キー再利用の判断が表に記録されている() -> None:
    # Arrange
    expected = {
        name for name, dialect in LIFECYCLE_DIALECTS.items() if dialect == "active_flag"
    }

    # Act
    actual = set(ACTIVE_FLAG_KEY_REUSE)

    # Assert: 再利用可否を決めずに is_active を足すことを許さない
    assert actual == expected
