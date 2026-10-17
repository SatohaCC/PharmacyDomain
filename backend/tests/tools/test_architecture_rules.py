"""アーキテクチャ規則を `uv run pytest` の一部として強制する。

`tools/` のチェッカは、実行されて初めて仕組みになります。pytest から呼ぶことで、
手元の `uv run pytest` と CI (`.github/workflows/quality-gate.yml`) の両方で
必ず実行されます。
"""

import tomllib
from pathlib import Path

from tools.check_fake_conformance import main as check_fake_conformance_main
from tools.check_imports import main as check_imports_main
from tools.check_lcom import main as check_lcom_main

_PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"


def test_care_eventは共有基盤や他Applicationコンテキストから独立している() -> None:
    """新しい業務コンテキストを各共通層の禁止規則へ登録する。"""
    config = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    forbidden = config["tool"]["import_rules"]["forbidden"]

    assert "app.domain.care_event" in forbidden["app.domain.foundation"]
    assert "app.domain.care_event" in forbidden["app.domain.shared"]
    assert "app.application.care_event" in forbidden["app.application.common"]
    for context in (
        "access_control",
        "corporate",
        "store",
        "staff",
        "patient",
        "coverage",
        "reception",
        "prescription",
        "dispensing",
        "medication_history",
        "medicine_catalog",
        "identity",
        "integration",
    ):
        package = f"app.application.{context}"
        assert package in forbidden, f"{package} に依存禁止規則がありません"
        assert "app.application.care_event" in forbidden[package], package


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


def test_テスト用Fakeが実装Protocolの全メンバを上書きしている() -> None:
    # Act
    exit_code = check_fake_conformance_main(
        ["--config", str(_PYPROJECT), "--fail-on-violation"]
    )

    # Assert
    assert exit_code == 0
