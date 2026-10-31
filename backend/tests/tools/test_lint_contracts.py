"""設定の存在だけでなく、実際の違反検出を確認する。"""

import json
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]


def _lint(
    tmp_path: Path, relative: str, source: str, *, boundaries: bool = False
) -> subprocess.CompletedProcess[str]:
    """一時プロジェクトで本番と同じRuff設定を評価する。"""
    (tmp_path / "pyproject.toml").write_text(
        (_ROOT / "pyproject.toml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    target = tmp_path / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source, encoding="utf-8")
    arguments = ["ruff", "check", "--no-cache", relative]
    if boundaries:
        scripts = json.loads((_ROOT / "package.json").read_text(encoding="utf-8"))[
            "scripts"
        ]
        arguments = shlex.split(scripts["lint:boundaries"])[2:]
        for layer in ("domain", "application"):
            (tmp_path / "app" / layer).mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        [sys.executable, "-m", *arguments],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


@pytest.mark.parametrize(
    "relative",
    [
        "app/example.py",
        "app/infrastructure/system_clock.py",
        "tools/check_fake_conformance.py",
        "migrations/versions/20260927_0010_care_events_and_generic_medication_history.py",
    ],
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
    tmp_path: Path, relative: str, source: str
) -> None:
    result = _lint(tmp_path, relative, source)

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
        ("import os  # noqa\n", "PGH004"),
        ("value = 1  # type: ignore\n", "PGH003"),
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


@pytest.mark.parametrize("layer", ["domain", "application", "infrastructure"])
@pytest.mark.parametrize(
    "source",
    [
        "import builtins as b\n\nb.__import__('app.infrastructure')\n",
        "from builtins import __import__ as load\n\nload('app.infrastructure')\n",
        "import importlib as loader\n\nloader.import_module('app.infrastructure')\n",
        "from importlib import import_module as load\n\nload('app.infrastructure')\n",
        "from typing import TYPE_CHECKING\n\nif TYPE_CHECKING:\n    from importlib import import_module as load\n\n    load('app.infrastructure')\n",
        "def execute():\n    from importlib import import_module as load\n\n    return load('app.infrastructure')\n",
    ],
)
def test_動的import_各層で別名や関数内に隠しても_禁止する(
    tmp_path: Path, layer: str, source: str
) -> None:
    result = _lint(tmp_path, f"app/{layer}/example.py", source)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "TID251" in result.stdout


@pytest.mark.parametrize(
    "relative",
    [
        "app/domain/example.py",
        "app/application/example.py",
        "app/infrastructure/example.py",
        "tests/test_example.py",
        "tools/example.py",
        "migrations/example.py",
    ],
)
@pytest.mark.parametrize(
    ("source", "rule"),
    [
        ("from .other import value\n\nprint(value)\n", "TID252"),
        ("from app.example import *\n", "F403"),
    ],
)
def test_import形式_各層で相対参照や全件参照を使うと_拒否する(
    tmp_path: Path, relative: str, source: str, rule: str
) -> None:
    result = _lint(tmp_path, relative, source)

    assert result.returncode == 1, result.stdout + result.stderr
    assert rule in result.stdout


@pytest.mark.parametrize(
    "source",
    [
        "import os  # noqa: F401\n",
        "value = 1  # type: ignore[assignment]\n",
        "from app.example import value\n\nprint(value)\n",
    ],
)
def test_明示した抑制と絶対import_許可形式は_拒否しない(
    tmp_path: Path, source: str
) -> None:
    result = _lint(tmp_path, "app/example.py", source)

    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("layer", ["domain", "application"])
@pytest.mark.parametrize(
    ("source", "rule"),
    [
        (
            "import builtins as b  # noqa: TID251\n\nb.__import__('app.infrastructure')\n",
            "TID251",
        ),
        (
            "from importlib import import_module as load  # noqa: TID251\n\nload('app.infrastructure')\n",
            "TID251",
        ),
        ("from .other import value  # noqa: TID252\n\nprint(value)\n", "TID252"),
        ("from app.example import *  # noqa: F403\n", "F403"),
        (
            "# ruff: noqa\nfrom datetime import date\n\nvalue = date.today()\n",
            "TID251",
        ),
    ],
)
def test_内側の境界規則_抑制コメントを付けても_標準ゲートが拒否する(
    tmp_path: Path, layer: str, source: str, rule: str
) -> None:
    result = _lint(tmp_path, f"app/{layer}/example.py", source, boundaries=True)

    assert result.returncode == 1, result.stdout + result.stderr
    assert rule in result.stdout


def test_通常lint_抑制できない境界検査を_必ず実行する() -> None:
    scripts = json.loads((_ROOT / "package.json").read_text(encoding="utf-8"))[
        "scripts"
    ]

    assert "pnpm run lint:boundaries" in scripts["lint"].split(" && ")
