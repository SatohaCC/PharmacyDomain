"""公開識別子が内部の業務型を公開しないことを確認する。"""

import ast
import importlib
import uuid
from pathlib import Path

import pytest

from app.domain.foundation.exceptions import DomainValidationError
from app.domain.foundation.primitives.identifiers import EntityStringId

_DOMAIN = Path(__file__).resolve().parents[2] / "app" / "domain"


def test_識別子_集約のID定義は_専用モジュールに置く() -> None:
    violations: list[str] = []
    for path in _DOMAIN.glob("*/*.py"):
        if path.parent.name in {"foundation", "shared"}:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.ClassDef)
                and path.name != "identifiers.py"
                and any(
                    isinstance(base, ast.Name) and base.id == "EntityUUID"
                    for base in node.bases
                )
            ):
                violations.append(f"{path.relative_to(_DOMAIN)}:{node.name}")
    assert not violations, violations


def test_公開ID_識別子以外の内部型へ_依存しない() -> None:
    modules = list(_DOMAIN.glob("*/identifiers.py"))
    assert modules, "公開IDモジュールがありません。"
    for path in modules:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom):
                assert node.module in {
                    "__future__",
                    "typing",
                    "app.domain.foundation.primitives.identifiers",
                }, (path, node.module)


def test_公開ID_定義を移動しても_生成と復元の契約を維持する() -> None:
    modules = list(_DOMAIN.glob("*/identifiers.py"))
    assert modules
    for path in modules:
        if path.parent.name in {"foundation", "shared"}:
            continue
        module = importlib.import_module(f"app.domain.{path.parent.name}.identifiers")
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            identifier = getattr(module, node.name)
            if issubclass(identifier, EntityStringId):
                original = identifier("テスト識別子")
                assert original == identifier.parse("テスト識別子")
                assert hash(original) == hash(identifier.parse("テスト識別子"))
                with pytest.raises(DomainValidationError):
                    identifier("")
                continue
            value = uuid.uuid7()
            original = identifier(value)
            restored = identifier.parse(str(value))
            assert original == restored
            assert hash(original) == hash(restored)
            assert original.value == value
            assert identifier.generate().value.version == 7
            with pytest.raises(DomainValidationError):
                identifier(uuid.uuid4())
