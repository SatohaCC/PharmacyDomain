"""アーキテクチャ規則を `uv run pytest` の一部として強制する。

`tools/` のチェッカは、実行されて初めて仕組みになります。CIが無い現状では
pytest が唯一必ず実行されるゲートなので、ここから呼び出します。
"""

from pathlib import Path

from tools.check_imports import main as check_imports_main
from tools.check_lcom import main as check_lcom_main

_PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"


def test_import方向ルールに違反がない() -> None:
    # Act
    exit_code = check_imports_main(["--config", str(_PYPROJECT), "--fail-on-violation"])

    # Assert
    assert exit_code == 0


def test_application層のLCOM4が閾値を超えていない() -> None:
    # Act
    exit_code = check_lcom_main(["--config", str(_PYPROJECT), "--fail-on-violation"])

    # Assert
    assert exit_code == 0
