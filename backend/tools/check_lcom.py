"""PythonのASTからクラスのLCOM4を計算する静的解析ツール。"""

from __future__ import annotations

import argparse
import ast
import json
import sys
import tomllib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PATHS = ("app/application",)


class LcomAnalysisError(Exception):
    """LCOM4の解析に失敗した場合の例外。"""


@dataclass(frozen=True, slots=True)
class LcomConfig:
    """LCOM4チェックの設定。"""

    paths: tuple[str, ...] = DEFAULT_PATHS
    threshold: int = 2
    min_methods: int = 2


@dataclass(frozen=True, slots=True)
class ClassMetric:
    """1クラス分のLCOM4測定結果。"""

    source_file: Path
    class_name: str
    line: int
    methods: tuple[str, ...]
    components: tuple[tuple[str, ...], ...]

    @property
    def lcom4(self) -> int:
        """メソッド間グラフの連結成分数を返す。"""
        return len(self.components)


@dataclass(frozen=True, slots=True)
class _MethodInfo:
    """LCOM4計算に必要なメソッドの参照情報。"""

    name: str
    line: int
    attributes: frozenset[str]
    calls: frozenset[str]


def _decorator_name(decorator: ast.expr) -> str | None:
    if isinstance(decorator, ast.Name):
        return decorator.id
    if isinstance(decorator, ast.Attribute):
        parent = _decorator_name(decorator.value)
        return f"{parent}.{decorator.attr}" if parent else decorator.attr
    if isinstance(decorator, ast.Call):
        return _decorator_name(decorator.func)
    return None


def _is_class_or_static_method(method: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    excluded = {"classmethod", "staticmethod"}
    return any(
        (_decorator_name(decorator) or "").rsplit(".", maxsplit=1)[-1] in excluded
        for decorator in method.decorator_list
    )


def _is_protocol_class(class_node: ast.ClassDef) -> bool:
    """状態を持たないProtocolを凝集度評価から除外する。"""
    return any(
        (_decorator_name(base) or "").rsplit(".", maxsplit=1)[-1] == "Protocol"
        for base in class_node.bases
    )


def _receiver_name(method: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    positional = [*method.args.posonlyargs, *method.args.args]
    if positional:
        return positional[0].arg
    if method.args.vararg is not None:
        return method.args.vararg.arg
    return None


class _MethodUsageVisitor(ast.NodeVisitor):
    """メソッド本体からインスタンス属性と内部呼び出しを抽出する。"""

    def __init__(self, receiver_name: str, local_methods: frozenset[str]) -> None:
        self._receiver_name = receiver_name
        self._local_methods = local_methods
        self.attributes: set[str] = set()
        self.calls: set[str] = set()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        # ネストした関数の引数でレシーバー名が隠れる可能性があるため、
        # 外側のメソッドの凝集度には含めない。
        return None

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        return None

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return None

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if isinstance(node.value, ast.Name) and node.value.id == self._receiver_name:
            self.attributes.add(node.attr)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        function = node.func
        if (
            isinstance(function, ast.Attribute)
            and isinstance(function.value, ast.Name)
            and function.value.id == self._receiver_name
            and function.attr in self._local_methods
        ):
            self.calls.add(function.attr)
        self.generic_visit(node)


def _method_info(
    method: ast.FunctionDef | ast.AsyncFunctionDef,
    local_methods: frozenset[str],
) -> _MethodInfo | None:
    receiver_name = _receiver_name(method)
    if receiver_name is None:
        return None

    visitor = _MethodUsageVisitor(receiver_name, local_methods)
    for statement in method.body:
        visitor.visit(statement)
    return _MethodInfo(
        name=method.name,
        line=method.lineno,
        attributes=frozenset(visitor.attributes),
        calls=frozenset(visitor.calls),
    )


def _class_methods(class_node: ast.ClassDef) -> tuple[_MethodInfo, ...]:
    method_nodes: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
    for statement in class_node.body:
        if not isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if statement.name == "__init__" or _is_class_or_static_method(statement):
            continue
        method_nodes[statement.name] = statement

    local_methods = frozenset(method_nodes)
    methods = [
        info
        for method in method_nodes.values()
        if (info := _method_info(method, local_methods)) is not None
    ]
    return tuple(sorted(methods, key=lambda method: (method.line, method.name)))


def _components(methods: Sequence[_MethodInfo]) -> tuple[tuple[str, ...], ...]:
    adjacency = {method.name: set[str]() for method in methods}
    for index, left in enumerate(methods):
        for right in methods[index + 1 :]:
            if left.attributes & right.attributes:
                adjacency[left.name].add(right.name)
                adjacency[right.name].add(left.name)

    for method in methods:
        for called_method in method.calls:
            adjacency[method.name].add(called_method)
            adjacency[called_method].add(method.name)

    remaining = set(adjacency)
    components: list[tuple[str, ...]] = []
    while remaining:
        start = min(remaining)
        stack = [start]
        component: set[str] = set()
        while stack:
            current = stack.pop()
            if current in component:
                continue
            component.add(current)
            stack.extend(adjacency[current] - component)
        remaining -= component
        components.append(tuple(sorted(component)))

    return tuple(sorted(components, key=lambda component: component[0]))


class _ClassCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.classes: list[tuple[str, ast.ClassDef]] = []
        self._class_stack: list[str] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._class_stack.append(node.name)
        self.classes.append((".".join(self._class_stack), node))
        self.generic_visit(node)
        self._class_stack.pop()


def analyze_source(
    source: str,
    *,
    source_file: Path = Path("<文字列>"),
    min_methods: int = 2,
) -> tuple[ClassMetric, ...]:
    """Pythonソースを解析し、測定対象クラスのLCOM4を返す。"""
    if min_methods < 1:
        raise ValueError("min_methods は1以上で指定してください。")

    try:
        tree = ast.parse(source, filename=str(source_file))
    except SyntaxError as error:
        raise LcomAnalysisError(
            f"Pythonの構文解析に失敗しました: {source_file}:{error.lineno}: {error.msg}"
        ) from error

    collector = _ClassCollector()
    collector.visit(tree)
    metrics: list[ClassMetric] = []
    for class_name, class_node in collector.classes:
        if _is_protocol_class(class_node):
            continue
        methods = _class_methods(class_node)
        if len(methods) < min_methods:
            continue
        metrics.append(
            ClassMetric(
                source_file=source_file,
                class_name=class_name,
                line=class_node.lineno,
                methods=tuple(method.name for method in methods),
                components=_components(methods),
            )
        )
    return tuple(metrics)


def collect_python_files(paths: Sequence[Path]) -> tuple[Path, ...]:
    """指定されたファイルまたはディレクトリからPythonファイルを列挙する。"""
    files: set[Path] = set()
    for path in paths:
        if path.is_file():
            if path.suffix == ".py":
                files.add(path)
            continue
        if not path.is_dir():
            raise FileNotFoundError(f"解析対象が見つかりません: {path}")
        files.update(
            candidate
            for candidate in path.rglob("*.py")
            if "__pycache__" not in candidate.parts
        )
    return tuple(sorted(files, key=lambda file: file.as_posix()))


def analyze_paths(
    paths: Sequence[Path],
    *,
    min_methods: int = 2,
) -> tuple[ClassMetric, ...]:
    """指定されたパス配下のPythonクラスを解析する。"""
    metrics: list[ClassMetric] = []
    for source_file in collect_python_files(paths):
        metrics.extend(
            analyze_source(
                source_file.read_text(encoding="utf-8"),
                source_file=source_file,
                min_methods=min_methods,
            )
        )
    return tuple(metrics)


def _string_tuple(value: object, *, key: str) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(
            f"[tool.lcom].{key} は文字列または文字列配列で指定してください。"
        )
    if not value:
        raise ValueError(f"[tool.lcom].{key} は1件以上指定してください。")
    return tuple(value)


def _positive_int(value: object, *, key: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"[tool.lcom].{key} は1以上の整数で指定してください。")
    return value


def load_config(config_path: Path = Path("pyproject.toml")) -> LcomConfig:
    """pyproject.tomlからLCOM4設定を読み込む。"""
    if not config_path.exists():
        return LcomConfig()

    with config_path.open("rb") as file:
        document = tomllib.load(file)
    tool_config = document.get("tool", {}).get("lcom", {})
    if not isinstance(tool_config, dict):
        raise ValueError("[tool.lcom] はテーブルとして指定してください。")

    # 既定値は tuple なので、未指定のときは _string_tuple を通さない。
    raw_paths = tool_config.get("paths")
    return LcomConfig(
        paths=(
            DEFAULT_PATHS
            if raw_paths is None
            else _string_tuple(raw_paths, key="paths")
        ),
        threshold=_positive_int(tool_config.get("threshold", 2), key="threshold"),
        min_methods=_positive_int(tool_config.get("min_methods", 2), key="min_methods"),
    )


def _resolved_paths(values: Sequence[str], base_dir: Path) -> tuple[Path, ...]:
    return tuple(
        (Path(value) if Path(value).is_absolute() else base_dir / value)
        for value in values
    )


def _metric_payload(metric: ClassMetric) -> dict[str, object]:
    return {
        "source_file": str(metric.source_file),
        "class_name": metric.class_name,
        "line": metric.line,
        "methods": list(metric.methods),
        "lcom4": metric.lcom4,
        "components": [list(component) for component in metric.components],
    }


def _print_report(
    metrics: Sequence[ClassMetric],
    *,
    threshold: int,
    verbose: bool,
) -> int:
    violations = [metric for metric in metrics if metric.lcom4 >= threshold]
    print(
        f"LCOM4チェック: {len(metrics)}クラスを評価、警告 {len(violations)}件 "
        f"（閾値: {threshold}）"
    )
    for metric in metrics:
        if not verbose and metric.lcom4 < threshold:
            continue
        level = "警告" if metric.lcom4 >= threshold else "情報"
        components = ", ".join("/".join(component) for component in metric.components)
        print(
            f"{level}: {metric.source_file}:{metric.line} "
            f"{metric.class_name} LCOM4={metric.lcom4} "
            f"（成分: {components}）"
        )
    if not violations:
        print("LCOM4の警告はありません。")
    return len(violations)


def _positive_int_argument(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("1以上の整数を指定してください。") from error
    if parsed < 1:
        raise argparse.ArgumentTypeError("1以上の整数を指定してください。")
    return parsed


def main(argv: Sequence[str] | None = None) -> int:
    """CLIエントリーポイント。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("pyproject.toml"),
        help="設定ファイルのパス（既定: pyproject.toml）",
    )
    parser.add_argument(
        "--path",
        nargs="+",
        help="解析対象。指定時は設定ファイルのpathsを上書きする。",
    )
    parser.add_argument("--threshold", type=_positive_int_argument)
    parser.add_argument("--min-methods", type=_positive_int_argument)
    parser.add_argument(
        "--verbose", action="store_true", help="警告以外の測定結果も表示する。"
    )
    parser.add_argument(
        "--json", action="store_true", help="測定結果をJSONで出力する。"
    )
    parser.add_argument(
        "--fail-on-violation",
        action="store_true",
        help="警告がある場合に終了コード1を返す。",
    )
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
        configured_paths = tuple(args.path) if args.path else config.paths
        threshold = args.threshold or config.threshold
        min_methods = args.min_methods or config.min_methods
        base_dir = args.config.parent.resolve()
        paths = _resolved_paths(configured_paths, base_dir)
        metrics = analyze_paths(paths, min_methods=min_methods)
    except (LcomAnalysisError, OSError, ValueError) as error:
        print(f"LCOM4チェックに失敗しました: {error}", file=sys.stderr)
        return 2

    if args.json:
        print(
            json.dumps(
                [_metric_payload(metric) for metric in metrics],
                ensure_ascii=False,
                indent=2,
            )
        )
        violations = sum(metric.lcom4 >= threshold for metric in metrics)
    else:
        violations = _print_report(
            metrics,
            threshold=threshold,
            verbose=args.verbose,
        )
    return 1 if args.fail_on_violation and violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
