"""循環が発生していたimport入口を新しいPython processで確認する。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "module",
    [
        ".".join(path.relative_to(_ROOT).with_suffix("").parts)
        for path in sorted((_ROOT / "app/domain").glob("*/*.py"))
        if path.parent.name not in {"foundation", "shared"}
        and path.name != "__init__.py"
    ],
)
def test_Domain具象モジュール_単独の新規processで_importできる(module: str) -> None:
    # Act
    result = subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        cwd=_ROOT,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
        timeout=30,
    )

    # Assert
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(
    ("command", "entrypoint"),
    [
        ((sys.executable, "-c", "import app.domain.dispensing"), "Domain調剤"),
        (
            (sys.executable, "-c", "import app.application.dispensing"),
            "Application調剤",
        ),
        (
            (
                sys.executable,
                "-m",
                "tools.check_fake_conformance",
                "--fail-on-violation",
            ),
            "Fake適合チェッカー",
        ),
    ],
)
def test_循環が発生した入口を新規processから起動できる(
    command: tuple[str, ...], entrypoint: str
) -> None:
    """pytest内の先行importで初期化済みになった状態を再利用しない。"""
    # Act
    result = subprocess.run(
        command,
        cwd=_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    # Assert
    assert result.returncode == 0, (
        f"{entrypoint}が新規processで失敗した。\n"
        f"標準出力: {result.stdout}\n標準エラー: {result.stderr}"
    )
