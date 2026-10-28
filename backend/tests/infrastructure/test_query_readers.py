"""参照アダプタが公開する契約と、更新処理との境界を検証する。"""

import ast
from pathlib import Path


def test_参照投影_Domainの業務サービスを直接呼び出さない() -> None:
    root = Path(__file__).resolve().parents[2] / "app/infrastructure/readers"
    paths = list(root.glob("*.py"))
    assert len(paths) >= 30
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
                "app.domain."
            ):
                assert not (node.module or "").endswith(".services"), path
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in {"save", "delete", "commit", "rollback"}, (
                    path
                )
