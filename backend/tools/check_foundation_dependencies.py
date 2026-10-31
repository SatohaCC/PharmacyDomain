"""共通基盤の標準ライブラリと内部依存の許可範囲を確認する。"""

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
