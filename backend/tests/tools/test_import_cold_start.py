"""循環が発生していたimport入口を新しいPython processで確認する。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]


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
