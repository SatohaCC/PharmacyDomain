"""プリミティブ・複合値・子エンティティの責務を分離する。"""

import ast
from pathlib import Path

_DOMAIN = Path(__file__).resolve().parents[2] / "app" / "domain"


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
