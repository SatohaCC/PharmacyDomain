"""共通基盤の標準ライブラリ制限と、動的importによる検査回避を確認する。"""

import ast
import sys
from importlib.util import resolve_name


def forbidden_imports(
    source: str,
    *,
    module: str,
    allowed_internal: tuple[str, ...],
    is_package: bool = False,
) -> tuple[str, ...]:
    """標準ライブラリと明示した内部基盤以外への依存を返す。"""
    violations: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            name = node.module or ""
            if node.level:
                package = module if is_package else module.rsplit(".", 1)[0]
                name = resolve_name("." * node.level + name, package)
            names = [name]
        else:
            continue
        for name in names:
            if name.split(".", 1)[0] in sys.stdlib_module_names:
                continue
            if any(
                name == prefix or name.startswith(prefix + ".")
                for prefix in allowed_internal
            ):
                continue
            violations.append(f"{node.lineno}:{name}")
    return tuple(violations)


def dynamic_import_calls(source: str) -> tuple[int, ...]:
    """直接・別名の動的import呼出しを返す。"""
    tree = ast.parse(source)
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                aliases[alias.asname or alias.name] = alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                aliases[alias.asname or alias.name] = f"{node.module}.{alias.name}"

    def qualified(node: ast.expr) -> str:
        if isinstance(node, ast.Name):
            return aliases.get(node.id, node.id)
        if isinstance(node, ast.Attribute):
            return f"{qualified(node.value)}.{node.attr}"
        return ""

    return tuple(
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and qualified(node.func)
        in {"__import__", "builtins.__import__", "importlib.import_module"}
    )
