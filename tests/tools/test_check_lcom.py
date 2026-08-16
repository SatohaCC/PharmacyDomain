from pathlib import Path

import pytest

from tools.check_lcom import (
    LcomAnalysisError,
    analyze_source,
    load_config,
    main,
)


def test_共通属性を使うメソッドは一つの成分になる() -> None:
    # Arrange
    source = """
class Cohesive:
    def first(self):
        return self._value

    def second(self):
        return self._value + 1
"""

    # Act
    metrics = analyze_source(source)

    # Assert
    assert len(metrics) == 1
    assert metrics[0].lcom4 == 1
    assert metrics[0].components == (("first", "second"),)


def test_異なる属性だけを使うメソッドは二つの成分になる() -> None:
    # Arrange
    source = """
class Split:
    def first(self):
        return self._first

    def second(self):
        return self._second
"""

    # Act
    metrics = analyze_source(source)

    # Assert
    assert metrics[0].lcom4 == 2
    assert metrics[0].components == (("first",), ("second",))


def test_内部メソッド呼び出しは属性がなくても成分をつなぐ() -> None:
    # Arrange
    source = """
class Connected:
    def execute(self):
        return self._build()

    def _build(self):
        return 1
"""

    # Act
    metrics = analyze_source(source)

    # Assert
    assert metrics[0].lcom4 == 1
    assert metrics[0].components == (("_build", "execute"),)


def test_初期化とクラスメソッドと静的メソッドを除外する() -> None:
    # Arrange
    source = """
class Measured:
    def __init__(self):
        self._ignored = 1

    @staticmethod
    def static_value():
        return 1

    @classmethod
    def class_value(cls):
        return 1

    def first(self):
        return self._first

    async def second(self):
        return self._second
"""

    # Act
    metrics = analyze_source(source)

    # Assert
    assert metrics[0].methods == ("first", "second")


def test_有効なメソッドが一つだけのクラスはスキップする() -> None:
    # Arrange
    source = """
class OneMethod:
    def execute(self):
        return 1
"""

    # Act
    metrics = analyze_source(source)

    # Assert
    assert metrics == ()


def test_構文エラーは解析例外になる() -> None:
    # Act / Assert
    with pytest.raises(LcomAnalysisError, match="Pythonの構文解析に失敗しました"):
        analyze_source("class Broken(:", source_file=Path("broken.py"))


def test_pyprojectの設定を読み込む(tmp_path: Path) -> None:
    # Arrange
    config_path = tmp_path / "pyproject.toml"
    config_path.write_text(
        """
[tool.lcom]
paths = ["src", "tests"]
threshold = 3
min_methods = 4
""",
        encoding="utf-8",
    )

    # Act
    config = load_config(config_path)

    # Assert
    assert config.paths == ("src", "tests")
    assert config.threshold == 3
    assert config.min_methods == 4


def test_警告だけでは既定で終了成功になる(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Arrange
    source_path = tmp_path / "split.py"
    source_path.write_text(
        """
class Split:
    def first(self):
        return self._first

    def second(self):
        return self._second
""",
        encoding="utf-8",
    )

    # Act
    exit_code = main(["--path", str(source_path)])

    # Assert
    assert exit_code == 0
    assert "警告 1件" in capsys.readouterr().out


def test_fail_on_violation指定時は終了コード一になる(
    tmp_path: Path,
) -> None:
    # Arrange
    source_path = tmp_path / "split.py"
    source_path.write_text(
        """
class Split:
    def first(self):
        return self._first

    def second(self):
        return self._second
""",
        encoding="utf-8",
    )

    # Act
    exit_code = main(["--path", str(source_path), "--fail-on-violation"])

    # Assert
    assert exit_code == 1
