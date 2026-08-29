"""集約のライフサイクル表現（方言）を凍結するゴールデンテスト。

現在、無効化の表し方は集約ごとに4通りに分かれている。日付つきの
``dated_activation`` が最も表現力が高いが、遡及判定を必要とする到達可能な
UseCase が存在しないため、いま全集約へ広げるのは先回りになる
（AGENTS.md「到達可能なClaim UseCaseがない間はClaim権限を定義しない」と同じ判断）。

そこで「統一しない」という判断そのものを機械で固定する。方言が5つ目に増えても、
新しい集約が増えても、既存集約の方言が変わっても、下の表を編集しない限り
pytest が落ちる。次に集約を足す人の目の前に必ずこの表が出てくる。

既知の限界: 分類はフィールド名と宣言型で行うため、``_DATED_ACTIVATION_VOCABULARIES``
にも ``is_active`` / ``status`` にも当てはまらない語彙（例 ``retirement: Retirement``）で
既存集約に無効化を実装すると ``none`` と分類され、表と一致してしまい検出できない。
一方、新しい集約は表に行が無いので必ず落ちる。最大の穴（集約が増えるたびに
方言が増える）は塞がっている。
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from dataclasses import fields, is_dataclass
from enum import Enum

import app.domain
from app.domain.foundation.entity import AggregateRoot

#: 許可するライフサイクル表現。
ALLOWED_DIALECTS = frozenset({"none", "active_flag", "status_enum", "dated_activation"})

#: 集約名 → ライフサイクル方言。実装を変えたらここも変える。
LIFECYCLE_DIALECTS: dict[str, str] = {
    "Corporate": "status_enum",
    "CoverageSelectionRecord": "none",
    # 調剤調製中 → 最終鑑査済 → 交付済 と進み、中止は別の終端になる。
    # 鑑査不合格は状態を戻さず ``IN_PROGRESS`` に留めるので、
    # 「不合格なのに交付できる」状態を作らずに再調製へ入れる。
    "DispensingProcess": "status_enum",
    # 薬歴は下書き→確定と進み、確定後の修正は追記（amend）で積む。
    # 遡って書き換えられる記録は3年保存の監査に耐えないため、状態を戻さない。
    "MedicationHistoryRecord": "status_enum",
    # 医薬品マスタは収載日〜経過措置期限で有効期間が決まる。期限当日までは
    # 使えるので閉区間であり、資格の半開区間とは区間の取り方が違う。
    "Medicine": "dated_activation",
    "Patient": "none",
    # 頭書きは薬歴からの投影なので「無効化」という状態を持たない。
    # 要素の終了は併用薬の ended_on など、要素側の期間で表す。
    "PatientMedicalProfile": "none",
    "PatientCoverage": "dated_activation",
    "PatientExternalIdentifier": "active_flag",
    # 受付済 → 調剤可能 → 調剤済 と進み、取消は別の終端になる。
    # 「疑義照会中」は状態にせず ``has_open_inquiry`` から導出しているので、
    # 方言は ``status_enum`` 1つに収まる。
    "Prescription": "status_enum",
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

#: ``dated_activation`` 方言として認めるフィールド名の組。
#:
#: 語彙は集約ごとに違う（資格は有効化/無効化、医薬品マスタは収載/経過措置）が、
#: 「日付で有効期間が決まる」という表現は同じである。1組だけを見る実装だと、
#: 別の語彙で日付つき無効化を実装した集約が ``none`` と誤分類され、表とも
#: 一致してしまって検出できない（この検出漏れは以前このファイルの
#: docstring が「既知の限界」として挙げていたもの）。
#:
_DATED_ACTIVATION_VOCABULARIES: tuple[frozenset[str], ...] = (
    frozenset({"activated_on", "deactivated_on"}),
    frozenset({"listed_on", "withdrawn_on"}),
)


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


def _is_dated_activation(annotation: type[object]) -> bool:
    """フィールドの型が、日付で有効期間を表す語彙のいずれかに合致するかを返す。"""
    field_names = {item.name for item in fields(annotation)}  # type: ignore[arg-type]
    return any(
        field_names >= vocabulary for vocabulary in _DATED_ACTIVATION_VOCABULARIES
    )


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
            and _is_dated_activation(annotation)
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
