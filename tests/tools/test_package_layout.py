"""Pythonパッケージに `__init__.py` があることを要求する。

`__init__.py` の無いディレクトリは名前空間パッケージになる。import 自体は
通るので普段は気づけないが、次の2つが「ある日突然」起きる。

1. そのディレクトリだけを指定して `pytest` を回すと、リポジトリルートが
   `sys.path` に入らず `ModuleNotFoundError: No module named 'app'` になる。
2. 別ディレクトリに同名のモジュールを置いた瞬間、トップレベル名が衝突して
   収集時に import エラーになる。

どちらも書いた本人ではなく後から触る人に出るため、構造の側で塞ぐ。
"""

from __future__ import annotations

from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]

# 1st party のパッケージルート。ここから下は全ディレクトリがパッケージである。
PACKAGE_ROOTS = ("app", "tests", "tools")


def _package_directories(root: Path) -> list[Path]:
    """ルート自身を含む、Pythonモジュールを持つディレクトリを集める。"""
    candidates = [root, *(path for path in root.rglob("*") if path.is_dir())]
    return [
        directory
        for directory in candidates
        if "__pycache__" not in directory.parts and any(directory.glob("*.py"))
    ]


@pytest.mark.parametrize("package_root", PACKAGE_ROOTS)
def test_パッケージ_全ディレクトリに__init__pyがある(package_root: str) -> None:
    # Arrange
    root = _ROOT / package_root
    assert root.is_dir(), f"パッケージルートが存在しない: {package_root}"

    # Act
    missing = [
        directory.relative_to(_ROOT).as_posix()
        for directory in _package_directories(root)
        if not (directory / "__init__.py").exists()
    ]

    # Assert
    assert not missing, f"`__init__.py` の無いディレクトリがある: {sorted(missing)}"


@pytest.mark.parametrize("package_root", PACKAGE_ROOTS)
def test_パッケージ_探索が1件以上のディレクトリを見つける(package_root: str) -> None:
    """探索が壊れたときに、無検査で緑になるのを防ぐ。"""
    # Act
    directories = _package_directories(_ROOT / package_root)

    # Assert
    assert directories, f"{package_root} 配下にPythonモジュールが1件も無い"
