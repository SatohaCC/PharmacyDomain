"""ユースケースの返却値が集約を素通しさせていないことを、全件に対して固定する。

Application層が集約をそのまま返すと、外側が集約の導出メソッドを直接呼べてしまう。
特に適用日を取る導出（``current_home_store_id`` 等）は、呼び出し側が日付を決める
ことになるので「いつ時点の値か」が経路ごとにばらける。返す形をIDか出力DTOに
限れば、この判断はApplication層の内側に留まる。

規約として書いても、新しいユースケースが1本入るたびに見落とせる。ここでは
``app/application`` 配下の ``*UseCase.execute`` を全部集めてから規則を当てる。
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
import typing
from collections.abc import Iterator
from types import ModuleType

import pytest

import app.application
from app.application.staff.register_staff import RegisterStaffUseCase
from app.domain.foundation.entity import Entity
from app.domain.staff.primitives import StaffId


def _use_case_classes(package: ModuleType) -> Iterator[type]:
    """パッケージ配下で定義されたユースケースクラスを集める。"""
    prefix = f"{package.__name__}."
    for module_info in pkgutil.walk_packages(package.__path__, prefix):
        module = importlib.import_module(module_info.name)
        for value in vars(module).values():
            if not isinstance(value, type) or not value.__name__.endswith("UseCase"):
                continue
            # 再エクスポートを二重に数えない。定義元のモジュールでだけ拾う。
            if value.__module__ != module_info.name:
                continue
            if not callable(getattr(value, "execute", None)):
                continue
            yield value


def _all_use_case_classes() -> list[type]:
    return sorted(
        set(_use_case_classes(app.application)),
        key=lambda klass: f"{klass.__module__}.{klass.__qualname__}",
    )


def _referenced_types(annotation: object) -> Iterator[type]:
    """注釈が名指しする具象クラスを、合併型・ジェネリクスの中まで含めて挙げる。"""
    if isinstance(annotation, type):
        yield annotation
    # ``get_args`` は ``X | None`` も ``list[X]`` も同じように展開する。
    for argument in typing.get_args(annotation):
        yield from _referenced_types(argument)


def _return_annotation(use_case: type) -> object:
    """``execute`` の戻り値注釈を、文字列注釈も解決したうえで返す。"""
    execute = use_case.execute  # type: ignore[attr-defined]
    hints = typing.get_type_hints(execute)
    if "return" not in hints:
        message = f"{use_case.__qualname__}.execute に戻り値の注釈がありません。"
        raise AssertionError(message)
    return hints["return"]


_USE_CASES = _all_use_case_classes()


def test_ユースケースの収集が_一定数以上を見つける() -> None:
    # 収集が壊れて0件になると、以下の検査が素通りする。
    assert len(_USE_CASES) >= 40


@pytest.mark.parametrize(
    "use_case", _USE_CASES, ids=lambda klass: f"{klass.__module__}.{klass.__name__}"
)
def test_ユースケースは_集約を返さない(use_case: type) -> None:
    # Arrange
    annotation = _return_annotation(use_case)

    # Act
    leaked = [
        referenced.__qualname__
        for referenced in _referenced_types(annotation)
        if issubclass(referenced, Entity)
    ]

    # Assert
    assert leaked == [], (
        f"{use_case.__qualname__}.execute が集約 {leaked} を返している。"
        "IDか出力DTOへ変換して返すこと。"
    )


@pytest.mark.asyncio
async def test_スタッフ登録は_採番されたIDだけを返す() -> None:
    # Arrange & Act
    annotation = _return_annotation(RegisterStaffUseCase)

    # Assert
    # 集約を返していた頃の呼び出し側は、適用日なしの導出を直接呼べていた。
    assert annotation is StaffId
    assert inspect.iscoroutinefunction(RegisterStaffUseCase.execute)
