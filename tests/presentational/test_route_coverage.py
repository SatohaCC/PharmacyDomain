"""配線したユースケースが、HTTPからも実行できることを固定する。

Composition Root への配線は `tests/infrastructure/test_composition.py` が網羅性を
検査しているが、そこを通ってもルートが無ければ外からは実行できない。ルータは
「足し忘れても既存のテストが全部通る」場所なので、網羅性そのものを検査する。
"""

from __future__ import annotations

import inspect
from collections.abc import Mapping
from types import ModuleType
from typing import Final, get_type_hints

from pydantic import BaseModel, ConfigDict, ValidationError

from app.application.prescription import DepartmentInput
from app.infrastructure.postgres import PostgresUseCaseRegistry
from app.presentational.routers import (
    corporate,
    coverage,
    dispensing,
    medication_history,
    medicine_catalog,
    patient,
    prescription,
    reception,
    staff,
    store,
)

#: 登録簿の束と、それを公開するルータモジュールの対応。
_ROUTER_FOR_BUNDLE: Final[Mapping[str, ModuleType]] = {
    "corporate": corporate,
    "store": store,
    "staff": staff,
    "patient": patient,
    "coverage": coverage,
    "reception": reception,
    "prescription": prescription,
    "dispensing": dispensing,
    "medication_history": medication_history,
    "medicine_catalog": medicine_catalog,
}


def test_登録簿の全コンテキストに_ルータがある() -> None:
    """束を足してルータを作り忘れると、そのコンテキストは外から使えない。"""
    # Act
    bundles = set(get_type_hints(PostgresUseCaseRegistry))

    # Assert
    assert bundles == set(_ROUTER_FOR_BUNDLE)


def test_全ユースケースが_HTTPルートから到達できる() -> None:
    """束へ足したユースケースにルートが無いと、配線だけされて実行できない。"""
    # Arrange
    bundle_types = get_type_hints(PostgresUseCaseRegistry)

    # Act
    unreachable = [
        f"{bundle_name}.{use_case_field}"
        for bundle_name, module in _ROUTER_FOR_BUNDLE.items()
        for use_case_field in get_type_hints(bundle_types[bundle_name])
        if f"use_cases.{use_case_field}." not in inspect.getsource(module)
    ]

    # Assert
    assert not unreachable, f"HTTPから実行できないユースケース: {unreachable}"


def test_到達性の検査が_一定数以上のユースケースを見ている() -> None:
    """走査が壊れて、何も検査しないまま緑になるのを防ぐ。"""
    # Arrange
    bundle_types = get_type_hints(PostgresUseCaseRegistry)

    # Act
    total = sum(len(get_type_hints(bundle)) for bundle in bundle_types.values())

    # Assert
    assert total >= 50


def test_入れ子の入力DTOでも_未知の項目を拒否する() -> None:
    """入れ子の本文は写し取らずApplication層のDTOをそのまま使う。

    そのぶん、外側のモデルに書いた「未知の項目を拒否する」設定が入れ子にも効くか
    は pydantic の挙動に依存する。効かなくなると、処方箋のような深い本文で
    打ち間違えた項目が黙って捨てられるので、挙動そのものを固定する。
    """

    # Arrange
    class Body(BaseModel):
        model_config = ConfigDict(extra="forbid")

        department: DepartmentInput

    # Act
    accepted = Body.model_validate({"department": {"code_type": "01", "name": "内科"}})
    rejected = False
    try:
        Body.model_validate(
            {"department": {"code_type": "01", "name": "内科", "nmae": "誤記"}}
        )
    except ValidationError:
        rejected = True

    # Assert
    assert accepted.department.name == "内科"
    assert rejected, "入れ子の未知項目が黙って捨てられている"
