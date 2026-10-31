"""設定の存在だけでなく、実際の違反検出を確認する。"""

import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]


def _lint(
    tmp_path: Path, relative: str, source: str
) -> subprocess.CompletedProcess[str]:
    """一時プロジェクトで本番と同じRuff設定を評価する。"""
    (tmp_path / "pyproject.toml").write_text(
        (_ROOT / "pyproject.toml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    target = tmp_path / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source, encoding="utf-8")
    return subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--no-cache", relative],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


@pytest.mark.parametrize(
    "source",
    [
        "from dataclasses import asdict\n\nasdict(object())\n",
        "from dataclasses import asdict as convert\n\nconvert(object())\n",
        "import dataclasses as dc\n\ndc.asdict(object())\n",
    ],
)
def test_辞書変換_本番で汎用変換を使うと_禁止API違反になる(
    tmp_path: Path, source: str
) -> None:
    result = _lint(tmp_path, "app/example.py", source)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "TID251" in result.stdout


def test_辞書変換_テストで使うと_禁止APIだけが除外される(tmp_path: Path) -> None:
    result = _lint(
        tmp_path,
        "tests/test_example.py",
        "from dataclasses import asdict\n\nasdict(object())\nmissing_name\n",
    )

    assert result.returncode == 1, result.stdout + result.stderr
    assert "TID251" not in result.stdout
    assert "F821" in result.stdout


@pytest.mark.parametrize(
    ("source", "rule"),
    [
        ("x = [value for value in range(3)]\n", "C416"),
        ("import os  # noqa: F401, F821\n", "RUF100"),
        ("class Example:\n    values = []\n", "RUF012"),
        ("import sys\nimport os\n\nprint(sys.path, os.name)\n", "I001"),
    ],
)
def test_追加規則_代表的な違反を入力すると_検出される(
    tmp_path: Path, source: str, rule: str
) -> None:
    result = _lint(tmp_path, "app/example.py", source)

    assert result.returncode == 1, result.stdout + result.stderr
    assert rule in result.stdout


def test_行長_長い文字列は_リンターで拒否しない(tmp_path: Path) -> None:
    result = _lint(tmp_path, "app/example.py", f'text = "{"a" * 120}"\n')

    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(
    "source",
    [
        "from datetime import datetime\n\ndatetime.now()\n",
        "import datetime\n\ndatetime.datetime.now()\n",
        "from datetime import date\n\ndate.today()\n",
        "import datetime\n\ndatetime.date.today()\n",
        "import time\n\ntime.time()\n",
        "from time import time\n\ntime()\n",
        "import importlib\n\nimportlib.import_module('app.infrastructure')\n",
        "from importlib import import_module\n\nimport_module('app.infrastructure')\n",
    ],
)
def test_環境日時と動的import_本番で直接呼ぶと_禁止API違反になる(
    tmp_path: Path, source: str
) -> None:
    result = _lint(tmp_path, "app/example.py", source)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "TID251" in result.stdout


def test_相対import_本番で使うと_相対import禁止違反になる(tmp_path: Path) -> None:
    result = _lint(
        tmp_path, "app/example.py", "from .other import value\nprint(value)\n"
    )

    assert result.returncode == 1, result.stdout + result.stderr
    assert "TID252" in result.stdout


@pytest.mark.parametrize(
    "source",
    [
        "from dataclasses import asdict\n\nasdict(object())\n",
        "from datetime import UTC, datetime\n\nx = datetime.now(UTC)\n",
        "import importlib\n\nimportlib.import_module('app.domain')\n",
    ],
)
def test_禁止API_インフラで使うと_違反になる(tmp_path: Path, source: str) -> None:
    result = _lint(tmp_path, "app/infrastructure/example.py", source)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "TID251" in result.stdout


def test_環境日時_実時計だけ明示除外すると_取得できる(tmp_path: Path) -> None:
    infra_result = _lint(
        tmp_path,
        "app/infrastructure/system_clock.py",
        (_ROOT / "app/infrastructure/system_clock.py").read_text(encoding="utf-8"),
    )
    assert infra_result.returncode == 0, infra_result.stdout + infra_result.stderr


def test_環境日時_テストで使うと_禁止APIが除外される(tmp_path: Path) -> None:
    test_result = _lint(
        tmp_path,
        "tests/test_example.py",
        "from datetime import date\n\nx = date.today()\n",
    )
    assert test_result.returncode == 0, test_result.stdout + test_result.stderr
