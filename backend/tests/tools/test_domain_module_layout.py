"""業務コンテキストのモジュール名を責務で統一する。"""

from pathlib import Path

import pytest

_DOMAIN = Path(__file__).resolve().parents[2] / "app" / "domain"
_ROLES = {
    "__init__.py",
    "identifiers.py",
    "exceptions.py",
    "primitives.py",
    "value_objects.py",
    "entities.py",
    "repositories.py",
    "services.py",
}


def _module_violations(domain: Path) -> list[str]:
    """基盤以外の全コンテキストから標準外のPython配置を集める。"""
    return sorted(
        path.relative_to(domain).as_posix()
        for context in domain.iterdir()
        if context.is_dir()
        and context.name not in {"foundation", "shared", "__pycache__"}
        for path in context.rglob("*.py")
        if "__pycache__" not in path.parts
        and (path.parent != context or path.name not in _ROLES)
    )


def test_Domainモジュール_全業務コンテキストが_役割別の直下配置を使う() -> None:
    # Act
    violations = _module_violations(_DOMAIN)

    # Assert
    assert not violations, f"役割別の標準配置でないモジュールがあります: {violations}"


@pytest.mark.parametrize(
    "filename", ["repository.py", "patient.py", "other.py", "nested/entities.py"]
)
def test_Domainモジュール_新設コンテキストの標準外配置を_検出する(
    tmp_path: Path, filename: str
) -> None:
    # Arrange
    path = tmp_path / "new_context" / filename
    path.parent.mkdir(parents=True)
    path.write_text("", encoding="utf-8")

    # Act
    violations = _module_violations(tmp_path)

    # Assert
    assert violations == [f"new_context/{filename}"]


def test_Domainモジュール_必要な標準配置だけなら_許可する(tmp_path: Path) -> None:
    # Arrange
    context = tmp_path / "new_context"
    context.mkdir()
    for filename in ("__init__.py", "entities.py", "repositories.py"):
        (context / filename).write_text("", encoding="utf-8")
    for name in ("foundation", "shared"):
        directory = tmp_path / name
        directory.mkdir()
        (directory / "custom.py").write_text("", encoding="utf-8")

    # Act
    violations = _module_violations(tmp_path)

    # Assert
    assert violations == []
