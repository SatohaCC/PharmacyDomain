"""プリミティブ・複合値・子エンティティの責務を分離する。"""

import ast
from pathlib import Path

import pytest

from tools.check_domain_architecture import role_violations as _role_violations

_DOMAIN = Path(__file__).resolve().parents[2] / "app" / "domain"


def test_Domainの役割別モジュール_定義の責務が_配置と一致する() -> None:
    # Act
    violations = [
        f"{path.parent.name}/{path.name}:{name}"
        for path in _DOMAIN.glob("*/*.py")
        if path.parent.name not in {"foundation", "shared"}
        for name in _role_violations(path.stem, path.read_text(encoding="utf-8"))
    ]

    # Assert
    assert not violations, violations


@pytest.mark.parametrize(
    ("role", "source"),
    [
        ("primitives", "class Sample(ValueObject): pass"),
        ("value_objects", "class Sample(Entity[SampleId]): pass"),
        ("value_objects", "class Sample(AggregateRoot[SampleId]): pass"),
        ("entities", "class Sample(Protocol): pass"),
        ("entities", "class SampleService: pass"),
    ],
)
def test_役割検査_誤った責務の定義を_検出する(role: str, source: str) -> None:
    # Act
    violations = _role_violations(role, source)

    # Assert
    assert len(violations) == 1


@pytest.mark.parametrize(
    ("role", "source"),
    [
        ("value_objects", "class Sample(ValueObject): pass"),
        ("entities", "class Sample(Entity[SampleId]): pass"),
        ("repositories", "class Sample(Protocol): pass"),
        ("services", "class SampleService: pass"),
    ],
)
def test_役割検査_責務が一致する定義を_許可する(role: str, source: str) -> None:
    # Act
    violations = _role_violations(role, source)

    # Assert
    assert violations == []


def test_プリミティブ_複合値の定義を_持たない() -> None:
    violations = []
    for path in _DOMAIN.glob("*/primitives.py"):
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if isinstance(node, ast.ClassDef) and any(
                isinstance(base, ast.Name)
                and base.id in {"ValueObject", "BaseQualificationProfile"}
                for base in node.bases
            ):
                violations.append(f"{path.parent.name}:{node.name}")
    assert not violations, violations


def test_複合値_子エンティティの定義を_持たない() -> None:
    violations = []
    for path in _DOMAIN.glob("*/value_objects.py"):
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if not isinstance(node, ast.ClassDef):
                continue
            for base in node.bases:
                name = base.value if isinstance(base, ast.Subscript) else base
                if isinstance(name, ast.Name) and name.id in {
                    "Entity",
                    "AggregateRoot",
                }:
                    violations.append(f"{path.parent.name}:{node.name}")
    assert not violations, violations
