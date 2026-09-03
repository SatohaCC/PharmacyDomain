"""任意項目のプリミティブ変換ヘルパーの契約を固定する。

``X.value if X is not None else None`` という定型は、1行に収まらず折り返されるため
DTOのフィールド構成そのものを定型に埋もれさせる。さらに、意味のある変換
（``Decimal`` を ``str`` へ落とす等）と単なる写しが同じ見た目になり、読み手が
注目すべき箇所を見分けられなくなる。

ここでは2つを守る。ヘルパーの振る舞いと、**定型が再び書かれていないこと**である。
後者を走査で固定しないと、次に項目が増えたときへ静かに戻る。
"""

from __future__ import annotations

import ast
import pathlib
from decimal import Decimal

import app.application
from app.application.common.optional_conversion import build_optional, unwrap
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.prescription import MedicalInstitutionPostalCode
from app.domain.shared.medicine import DosageAmount

#: 走査から除く実装。ヘルパー自身は定型そのものを持つ。
_EXCLUDED = {"optional_conversion.py"}


def test_unwrap_プリミティブを渡すと_保持する値が返る() -> None:
    # Arrange
    primitive = MedicalInstitutionPostalCode("1000001")

    # Act
    actual = unwrap(primitive)

    # Assert
    assert actual == "100-0001"


def test_unwrap_Noneを渡すと_Noneが返る() -> None:
    # Arrange
    primitive: MedicalInstitutionPostalCode | None = None

    # Act
    actual = unwrap(primitive)

    # Assert
    assert actual is None


def test_unwrap_Decimalを持つプリミティブは_Decimalのまま返る() -> None:
    """``float`` へ落とすと0.05刻みの用量で誤差が入る。"""
    # Arrange
    primitive = DosageAmount(Decimal("0.05"))

    # Act
    actual = unwrap(primitive)

    # Assert
    assert actual is not None
    assert actual * 3 == DosageAmount(Decimal("0.15")).value


def test_build_optional_値があると_プリミティブが生成される() -> None:
    # Arrange
    raw = "1000001"

    # Act
    actual = build_optional(raw, MedicalInstitutionPostalCode)

    # Assert
    assert actual == MedicalInstitutionPostalCode("1000001")


def test_build_optional_前後の余白は_取り除かれる() -> None:
    # Arrange
    raw = "  1000001  "

    # Act
    actual = build_optional(raw, MedicalInstitutionPostalCode)

    # Assert
    assert actual == MedicalInstitutionPostalCode("1000001")


def test_build_optional_空白のみは_未設定として扱う() -> None:
    """空文字を「不正な値」ではなく「項目解除」と読む。"""
    # Arrange
    raw = "   "

    # Act
    actual = build_optional(raw, MedicalInstitutionPostalCode)

    # Assert
    assert actual is None


def test_build_optional_Noneは_生成せずNoneが返る() -> None:
    # Arrange
    raw: str | None = None

    # Act
    actual = build_optional(raw, MedicalInstitutionPostalCode)

    # Assert
    assert actual is None


def test_build_optional_値が不正なら_ドメイン例外が伝わる() -> None:
    """未設定は握り潰すが、入力された不正値は握り潰さない。"""
    # Arrange
    raw = "12345"

    # Act & Assert
    try:
        build_optional(raw, MedicalInstitutionPostalCode)
    except DomainValidationError:
        return
    raise AssertionError("不正な郵便番号が検証されずに通った。")


def _redundant_optional_unwraps(source: str) -> list[str]:
    """``X.value if X is not None else None`` の形をした条件式を集める。

    両辺が同一の式である場合だけを対象にする。``value.split.count.value if
    value.split is not None else None`` のように判定対象と取り出す対象がずれる
    条件式は、``unwrap`` では表せない本物の条件なので拾わない。
    """
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.IfExp):
            continue
        if not (isinstance(node.orelse, ast.Constant) and node.orelse.value is None):
            continue
        test = node.test
        if not (
            isinstance(test, ast.Compare)
            and len(test.ops) == 1
            and isinstance(test.ops[0], ast.IsNot)
            and isinstance(test.comparators[0], ast.Constant)
            and test.comparators[0].value is None
        ):
            continue
        body = node.body
        if not (isinstance(body, ast.Attribute) and body.attr == "value"):
            continue
        if ast.dump(body.value) == ast.dump(test.left):
            found.append(ast.unparse(node))
    return found


def test_Application層に_unwrapで置き換えられる定型が残っていない() -> None:
    """定型が戻ったら落とす。レビューは仕組みではない。"""
    # Arrange
    root = pathlib.Path(app.application.__path__[0])

    # Act
    offenders = {
        str(path.relative_to(root)): expressions
        for path in sorted(root.rglob("*.py"))
        if path.name not in _EXCLUDED
        and (expressions := _redundant_optional_unwraps(path.read_text("utf-8")))
    }

    # Assert
    assert offenders == {}, f"``unwrap()`` で1行にできる定型が残っている: {offenders}"
