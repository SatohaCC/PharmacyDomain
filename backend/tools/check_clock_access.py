"""業務モデルが実行環境の日時を暗黙に取得しないことを検査する。"""

import ast
from pathlib import Path

_AMBIENT_CALLS = frozenset(
    {
        "datetime.date.today",
        "datetime.datetime.today",
        "datetime.datetime.now",
        "datetime.datetime.utcnow",
        "datetime.datetime.utcfromtimestamp",
        "time.time",
        "time.time_ns",
        "time.localtime",
        "time.gmtime",
    }
)


def find_ambient_clock_calls(source: str) -> tuple[int, ...]:
    """直接importと別名importによる環境日時の取得行を返す。"""
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
        if isinstance(node, ast.Call) and qualified(node.func) in _AMBIENT_CALLS
    )


def check_paths(root: Path) -> tuple[str, ...]:
    """DomainとApplicationの環境日時参照を列挙する。"""
    return tuple(
        f"{path.relative_to(root).as_posix()}:{line}"
        for layer in ("domain", "application")
        for path in sorted((root / "app" / layer).rglob("*.py"))
        for line in find_ambient_clock_calls(path.read_text(encoding="utf-8"))
    )
