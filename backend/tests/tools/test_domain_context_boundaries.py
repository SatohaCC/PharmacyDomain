"""全コンテキストで公開IDだけを越境参照できることを確認する。"""

import ast
from pathlib import Path


def test_Domain越境_他コンテキストの実装型は_参照しない() -> None:
    root = Path(__file__).resolve().parents[2] / "app" / "domain"
    violations = []
    for path in root.glob("*/*.py"):
        context = path.parent.name
        if context in {"foundation", "shared"}:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.ImportFrom) or not node.module:
                continue
            parts = node.module.split(".")
            if parts[:2] != ["app", "domain"] or len(parts) < 3:
                continue
            if parts[2] in {context, "foundation", "shared"}:
                continue
            if node.module != f"app.domain.{parts[2]}.identifiers":
                violations.append(
                    f"{path.relative_to(root)}:{node.lineno}:{node.module}"
                )
    assert not violations, violations
