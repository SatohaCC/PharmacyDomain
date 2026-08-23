"""フェイク適合性チェッカ自体の単体テスト。"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

from tools.check_fake_conformance import (
    FakeConformanceError,
    analyze_module,
    load_config,
    main,
)

_MODULE_COUNTER = iter(range(1000))


def _write_module(tmp_path: Path, source: str) -> str:
    """一時ディレクトリへモジュールを書き出し、import 可能にして名前を返す。"""
    module_name = f"_fake_conformance_probe_{next(_MODULE_COUNTER)}"
    (tmp_path / f"{module_name}.py").write_text(
        textwrap.dedent(source), encoding="utf-8"
    )
    if str(tmp_path) not in sys.path:
        sys.path.insert(0, str(tmp_path))
    sys.modules.pop(module_name, None)
    return module_name


_PROTOCOL_SOURCE = """
    from typing import Protocol


    class SampleRepository(Protocol):
        async def get(self, key: str) -> str | None:
            ...

        async def save(self, key: str, value: str) -> None:
            ...
"""


def test_未実装メンバを持つフェイクは_違反として検出される(tmp_path: Path) -> None:
    # Arrange
    module_name = _write_module(
        tmp_path,
        _PROTOCOL_SOURCE
        + """

    class PartialFake(SampleRepository):
        async def get(self, key: str) -> str | None:
            return None
""",
    )

    # Act
    violations = analyze_module(module_name)

    # Assert
    assert len(violations) == 1
    assert violations[0].class_name == "PartialFake"
    assert violations[0].member_name == "save"


def test_全メンバを実装したフェイクは_違反にならない(tmp_path: Path) -> None:
    # Arrange
    module_name = _write_module(
        tmp_path,
        _PROTOCOL_SOURCE
        + """

    class CompleteFake(SampleRepository):
        async def get(self, key: str) -> str | None:
            return None

        async def save(self, key: str, value: str) -> None:
            return None
""",
    )

    # Act
    violations = analyze_module(module_name)

    # Assert
    assert violations == ()


def test_Protocolを継承していないクラスは_検査対象にならない(tmp_path: Path) -> None:
    # Arrange
    module_name = _write_module(
        tmp_path,
        _PROTOCOL_SOURCE
        + """

    class Unrelated:
        async def get(self, key: str) -> str | None:
            return None
""",
    )

    # Act
    violations = analyze_module(module_name)

    # Assert
    assert violations == ()


def test_基底クラス経由で実装していれば_違反にならない(tmp_path: Path) -> None:
    # Arrange
    module_name = _write_module(
        tmp_path,
        _PROTOCOL_SOURCE
        + """

    class SaveMixin:
        async def save(self, key: str, value: str) -> None:
            return None


    class MixedFake(SaveMixin, SampleRepository):
        async def get(self, key: str) -> str | None:
            return None
""",
    )

    # Act
    violations = analyze_module(module_name)

    # Assert
    assert violations == ()


def test_import不能なモジュールは_解析エラーになる(tmp_path: Path) -> None:
    # Arrange
    module_name = _write_module(tmp_path, "\nimport module_that_does_not_exist\n")

    # Act / Assert
    with pytest.raises(FakeConformanceError):
        analyze_module(module_name)


def test_設定ファイルが無いと_既定のpathsになる(tmp_path: Path) -> None:
    # Arrange / Act
    actual = load_config(tmp_path / "absent.toml")

    # Assert
    assert actual.paths == ("tests/fakes",)
    assert actual.root == "."


def test_pathsが文字列配列でないと_値エラーになる(tmp_path: Path) -> None:
    # Arrange
    config_path = tmp_path / "pyproject.toml"
    config_path.write_text("[tool.fake_rules]\npaths = 1\n", encoding="utf-8")

    # Act / Assert
    with pytest.raises(ValueError):
        load_config(config_path)


def test_違反があっても_fail_on_violation無しなら終了コード0になる(
    tmp_path: Path,
) -> None:
    # Arrange
    module_name = _write_module(
        tmp_path,
        _PROTOCOL_SOURCE
        + """

    class PartialFake(SampleRepository):
        async def get(self, key: str) -> str | None:
            return None
""",
    )
    config_path = tmp_path / "pyproject.toml"
    config_path.write_text("[tool.fake_rules]\nroot = '.'\n", encoding="utf-8")

    # Act
    exit_code = main(["--config", str(config_path), "--path", f"{module_name}.py"])

    # Assert
    assert exit_code == 0


def test_違反があり_fail_on_violation付きなら終了コード1になる(
    tmp_path: Path,
) -> None:
    # Arrange
    module_name = _write_module(
        tmp_path,
        _PROTOCOL_SOURCE
        + """

    class PartialFake(SampleRepository):
        async def get(self, key: str) -> str | None:
            return None
""",
    )
    config_path = tmp_path / "pyproject.toml"
    config_path.write_text("[tool.fake_rules]\nroot = '.'\n", encoding="utf-8")

    # Act
    exit_code = main(
        [
            "--config",
            str(config_path),
            "--path",
            f"{module_name}.py",
            "--fail-on-violation",
        ]
    )

    # Assert
    assert exit_code == 1
