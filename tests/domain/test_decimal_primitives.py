"""Shared Kernel の十進数プリミティブのテスト。

用量に ``float`` を使うと「各回服用量の合計が1日量と一致する」不変条件が
正当な処方を弾く。この事実そのものを :func:`test_十進数_実在する用量刻みの合計が_誤差なく一致する`
で固定しているので、将来 ``float`` へ戻す変更は必ず落ちる。
"""

from __future__ import annotations

from decimal import Decimal
from itertools import product
from typing import ClassVar

import pytest

from app.domain.foundation.exceptions import DomainValidationError
from app.domain.foundation.primitives.primitives import (
    BaseNonNegativeDecimal,
    BasePositiveDecimal,
)


class _TestAmount(BasePositiveDecimal):
    """検証用の具象クラス（整数部6桁・小数部5桁）。"""

    max_integer_digits: ClassVar[int] = 6
    max_decimal_places: ClassVar[int] = 5
    quantity_name: ClassVar[str] = "分量"


class _TestNonNegative(BaseNonNegativeDecimal):
    """0を許容する検証用の具象クラス。"""

    max_integer_digits: ClassVar[int] = 3
    max_decimal_places: ClassVar[int] = 2
    quantity_name: ClassVar[str] = "点数"


# 実在する用量刻み。0.05刻みは散剤・液剤で、0.25/0.5は錠剤の分割で日常的に現れる。
_REAL_DOSAGE_STEPS = (
    "0.05",
    "0.1",
    "0.15",
    "0.2",
    "0.25",
    "0.3",
    "0.4",
    "0.5",
    "0.6",
    "0.7",
    "0.75",
    "0.8",
    "0.9",
    "1.0",
    "1.25",
    "1.5",
    "2.0",
    "2.5",
    "3.0",
)


def test_十進数_実在する用量刻みの合計が_誤差なく一致する() -> None:
    """不均等服用の合計判定が全組み合わせで成立することを固定する。

    同じ総当りを ``float`` で行うと 6,859 通り中 869 通り（12.7%）で
    合計が一致せず、正当な処方が弾かれる。
    """
    # Arrange
    combinations = list(product(_REAL_DOSAGE_STEPS, repeat=3))

    # Act
    mismatched = [
        (morning, noon, evening)
        for morning, noon, evening in combinations
        if _TestAmount.parse(morning).value
        + _TestAmount.parse(noon).value
        + _TestAmount.parse(evening).value
        != Decimal(morning) + Decimal(noon) + Decimal(evening)
    ]

    # Assert
    assert combinations, "総当りの組み合わせが生成されていない"
    assert mismatched == []


def test_十進数_同じ刻みを3回足しても_期待値と一致する() -> None:
    """``float`` で最初に壊れる具体例（0.05 × 3）を名前つきで残す。"""
    # Arrange
    step = _TestAmount.parse("0.05")

    # Act
    total = step.value + step.value + step.value

    # Assert: float なら 0.15000000000000002 になる
    assert total == Decimal("0.15")


@pytest.mark.parametrize("raw", ["1.5", 2, Decimal("0.25")])
def test_十進数_文字列と整数とDecimalから_生成できる(raw: str | int | Decimal) -> None:
    # Arrange / Act
    actual = _TestAmount.parse(raw)

    # Assert
    assert actual.value == Decimal(str(raw))


def test_十進数_floatを渡すと_誤差混入前に拒否される() -> None:
    """``float`` は受け取った時点で誤差を持つため、境界で弾く。"""
    # Arrange / Act / Assert
    with pytest.raises(DomainValidationError, match="float"):
        _TestAmount(0.1)  # type: ignore[arg-type]


def test_十進数_真偽値を渡すと_数値として拒否される() -> None:
    # Arrange / Act / Assert
    with pytest.raises(DomainValidationError, match="数値"):
        _TestAmount(True)  # type: ignore[arg-type]


@pytest.mark.parametrize("raw", ["NaN", "Infinity", "-Infinity"])
def test_十進数_有限でない値は_拒否される(raw: str) -> None:
    # Arrange / Act / Assert
    with pytest.raises(DomainValidationError, match="有限"):
        _TestAmount.parse(raw)


def test_十進数_数値として解釈できない文字列は_拒否される() -> None:
    # Arrange / Act / Assert
    with pytest.raises(DomainValidationError, match="解釈"):
        _TestAmount.parse("１錠")


def test_十進数_小数部が規定を超えると_拒否される() -> None:
    # Arrange / Act / Assert
    with pytest.raises(DomainValidationError, match="小数部"):
        _TestAmount.parse("1.123456")


def test_十進数_整数部が規定を超えると_拒否される() -> None:
    # Arrange / Act / Assert
    with pytest.raises(DomainValidationError, match="整数部"):
        _TestAmount.parse("1234567")


def test_十進数_指数表記でも整数部の桁数が数えられる() -> None:
    """``1E+7`` は係数1桁だが整数部は8桁である。"""
    # Arrange / Act / Assert
    with pytest.raises(DomainValidationError, match="整数部"):
        _TestAmount.parse("1E+7")


def test_十進数_0以下は正の値として拒否される() -> None:
    # Arrange / Act / Assert
    with pytest.raises(DomainValidationError, match="正の値"):
        _TestAmount.parse("0")


def test_十進数_0以上の基底では_0を受け入れる() -> None:
    # Arrange / Act
    actual = _TestNonNegative.parse("0")

    # Assert
    assert actual.value == Decimal("0")


def test_十進数_0以上の基底でも_負値は拒否される() -> None:
    # Arrange / Act / Assert
    with pytest.raises(DomainValidationError, match="0以上"):
        _TestNonNegative.parse("-0.01")


def test_十進数_末尾の0の有無にかかわらず_同値になる() -> None:
    """``1.50`` と ``1.5`` は等価。表記は保持するが比較には影響しない。"""
    # Arrange / Act
    padded = _TestAmount.parse("1.50")
    plain = _TestAmount.parse("1.5")

    # Assert
    assert padded == plain
    assert hash(padded) == hash(plain)


def test_十進数_エラーメッセージに_項目名が含まれる() -> None:
    """派生クラスの ``quantity_name`` が利用者に見えることを固定する。"""
    # Arrange / Act / Assert
    with pytest.raises(DomainValidationError, match="点数"):
        _TestNonNegative.parse("-1")


def test_十進数_floatから作ったDecimalは_桁数上限が弾く() -> None:
    """``Decimal(0.1)`` は小数部55桁になるため、桁数上限が誤差を検出する。

    コンストラクタは ``Decimal`` を受け取るので型では止まらないが、
    float 由来の値はここで落ちる。

    ruff の RUF032 が ``Decimal()`` への float リテラルを禁止しているため、
    「lint をすり抜けた場合でも実行時に落ちる」ことを確かめる意図で noqa する。
    """
    # Arrange / Act / Assert
    with pytest.raises(DomainValidationError, match="小数部"):
        _TestAmount(Decimal(0.1))  # noqa: RUF032


def test_十進数_二進で厳密な値なら_floatから作っても通る() -> None:
    """``0.5`` は二進で厳密に表現できるため誤差を持たない。

    「float 由来を一律で拒否している」のではなく「誤差のある値だけを
    弾いている」ことを示す対の記録。RUF032 の noqa は上と同じ理由。
    """
    # Arrange / Act
    actual = _TestAmount(Decimal(0.5))  # noqa: RUF032

    # Assert
    assert actual.value == Decimal("0.5")
