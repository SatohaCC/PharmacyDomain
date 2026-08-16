"""PythonのASTから import の依存方向を検証する静的解析ツール。

`pyproject.toml` の `[tool.import_rules.forbidden]` に「このパッケージから
import してはいけないモジュール接頭辞」を宣言し、違反を検出します。
AGENTS.md の「依存の向き」「Applicationコンテキストの依存」を実行可能にすることが目的です。

判定は保守的（fail-safe）に寄せています。

- `if TYPE_CHECKING:` の中の import も違反として扱います。実行時の依存は無くても、
  設計上の依存方向は同じく壊れるためです。
- `from app.application import store` のように親モジュールから名前を取り出す形も、
  `app.application.store` を import したものとして扱います。
- 相対 import は絶対モジュール名へ解決します。解決できない場合は例外にします。
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
import tomllib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

DEFAULT_ROOT = "."
DEFAULT_PATHS = ("app",)


class ImportAnalysisError(Exception):
    """import 方向の解析に失敗した場合の例外。"""


@dataclass(frozen=True, slots=True)
class ImportRule:
    """1つのパッケージに課す import 禁止ルール。"""

    package: str
    forbidden: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ImportRulesConfig:
    """import 方向チェックの設定。"""

    root: str = DEFAULT_ROOT
    paths: tuple[str, ...] = DEFAULT_PATHS
    rules: tuple[ImportRule, ...] = ()


@dataclass(frozen=True, slots=True)
class ImportViolation:
    """検出された1件の依存方向違反。"""

    source_file: Path
    line: int
    module_name: str
    imported: str
    package: str
    forbidden: str

    def describe(self) -> str:
        """人が読める1行の違反説明を返す。"""
        return (
            f"{self.source_file}:{self.line} "
            f"{self.module_name} は {self.imported} を import しています"
            f"（規則: {self.package} → {self.forbidden} は禁止）"
        )


def is_within(module: str, package: str) -> bool:
    """モジュールが指定パッケージ配下（自身を含む）にあるかを返す。"""
    return module == package or module.startswith(f"{package}.")


def module_name_for(source_file: Path, root: Path) -> tuple[str, bool]:
    """ソースファイルのパスから、ドット区切りのモジュール名とパッケージ判定を返す。"""
    try:
        relative = source_file.resolve().relative_to(root.resolve())
    except ValueError as error:
        raise ImportAnalysisError(
            f"解析対象がルート外にあります: {source_file}（ルート: {root}）"
        ) from error

    parts = list(relative.parts)
    is_package = parts[-1] == "__init__.py"
    parts[-1] = parts[-1].removesuffix(".py")
    if is_package:
        parts.pop()
    if not parts:
        raise ImportAnalysisError(f"モジュール名を決定できません: {source_file}")
    return ".".join(parts), is_package


def _resolve_relative(
    *,
    module_name: str,
    is_package: bool,
    node_module: str | None,
    level: int,
    source_file: Path,
    line: int,
) -> str:
    parts = module_name.split(".")
    if not is_package:
        parts = parts[:-1]

    if level - 1 > len(parts):
        raise ImportAnalysisError(
            f"相対 import を解決できません: {source_file}:{line}"
            f"（モジュール: {module_name}、レベル: {level}）"
        )

    base = parts[: len(parts) - (level - 1)]
    if node_module:
        base = [*base, *node_module.split(".")]
    if not base:
        raise ImportAnalysisError(
            f"相対 import を解決できません: {source_file}:{line}"
            f"（モジュール: {module_name}、レベル: {level}）"
        )
    return ".".join(base)


def _imported_modules(
    tree: ast.Module,
    *,
    module_name: str,
    is_package: bool,
    source_file: Path,
) -> tuple[tuple[str, int], ...]:
    """構文木から、import されたモジュール名と行番号の組を列挙する。"""
    imported: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend((alias.name, node.lineno) for alias in node.names)
            continue
        if not isinstance(node, ast.ImportFrom):
            continue

        if node.level:
            resolved = _resolve_relative(
                module_name=module_name,
                is_package=is_package,
                node_module=node.module,
                level=node.level,
                source_file=source_file,
                line=node.lineno,
            )
        elif node.module:
            resolved = node.module
        else:
            continue

        imported.append((resolved, node.lineno))
        # `from app.application import store` を app.application.store の import として扱う。
        imported.extend(
            (f"{resolved}.{alias.name}", node.lineno)
            for alias in node.names
            if alias.name != "*"
        )
    return tuple(imported)


def analyze_source(
    source: str,
    *,
    module_name: str,
    rules: Sequence[ImportRule],
    source_file: Path = Path("<文字列>"),
    is_package: bool = False,
) -> tuple[ImportViolation, ...]:
    """Pythonソースを解析し、依存方向に違反する import を返す。"""
    try:
        tree = ast.parse(source, filename=str(source_file))
    except SyntaxError as error:
        raise ImportAnalysisError(
            f"Pythonの構文解析に失敗しました: {source_file}:{error.lineno}: {error.msg}"
        ) from error

    applicable = [rule for rule in rules if is_within(module_name, rule.package)]
    if not applicable:
        return ()

    imported = _imported_modules(
        tree,
        module_name=module_name,
        is_package=is_package,
        source_file=source_file,
    )

    violations: list[ImportViolation] = []
    seen: set[tuple[str, str, int]] = set()
    for name, line in imported:
        for rule in applicable:
            for forbidden in rule.forbidden:
                if not is_within(name, forbidden):
                    continue
                key = (rule.package, forbidden, line)
                if key in seen:
                    continue
                seen.add(key)
                violations.append(
                    ImportViolation(
                        source_file=source_file,
                        line=line,
                        module_name=module_name,
                        imported=name,
                        package=rule.package,
                        forbidden=forbidden,
                    )
                )
    return tuple(
        sorted(violations, key=lambda violation: (violation.line, violation.imported))
    )


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
    root: Path,
    rules: Sequence[ImportRule],
) -> tuple[ImportViolation, ...]:
    """指定されたパス配下のPythonファイルの import 方向を検証する。"""
    violations: list[ImportViolation] = []
    for source_file in collect_python_files(paths):
        module_name, is_package = module_name_for(source_file, root)
        violations.extend(
            analyze_source(
                source_file.read_text(encoding="utf-8"),
                module_name=module_name,
                rules=rules,
                source_file=source_file,
                is_package=is_package,
            )
        )
    return tuple(violations)


def _string_tuple(value: object, *, key: str) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(
            f"[tool.import_rules].{key} は文字列または文字列配列で指定してください。"
        )
    if not value:
        raise ValueError(f"[tool.import_rules].{key} は1件以上指定してください。")
    return tuple(value)


def _parse_rules(value: object) -> tuple[ImportRule, ...]:
    if not isinstance(value, dict):
        raise ValueError(
            "[tool.import_rules.forbidden] はテーブルとして指定してください。"
        )

    rules: list[ImportRule] = []
    for package, forbidden in value.items():
        if not package:
            raise ValueError(
                "[tool.import_rules.forbidden] のキーはパッケージ名で指定してください。"
            )
        prefixes = _string_tuple(forbidden, key=f"forbidden.{package}")
        for prefix in prefixes:
            # 禁止先が自パッケージの祖先だと、内部 import まで全て違反になる。
            if is_within(package, prefix):
                raise ValueError(
                    f"[tool.import_rules.forbidden].{package} に自身を含む接頭辞 "
                    f"'{prefix}' が指定されています。"
                )
        rules.append(ImportRule(package=package, forbidden=prefixes))
    return tuple(sorted(rules, key=lambda rule: rule.package))


def load_config(config_path: Path = Path("pyproject.toml")) -> ImportRulesConfig:
    """pyproject.tomlから import 方向チェックの設定を読み込む。"""
    if not config_path.exists():
        return ImportRulesConfig()

    with config_path.open("rb") as file:
        document = tomllib.load(file)
    tool_config = document.get("tool", {}).get("import_rules", {})
    if not isinstance(tool_config, dict):
        raise ValueError("[tool.import_rules] はテーブルとして指定してください。")

    root = tool_config.get("root", DEFAULT_ROOT)
    if not isinstance(root, str) or not root:
        raise ValueError("[tool.import_rules].root は文字列で指定してください。")

    # 既定値は tuple なので、未指定のときは _string_tuple を通さない。
    raw_paths = tool_config.get("paths")
    return ImportRulesConfig(
        root=root,
        paths=(
            DEFAULT_PATHS
            if raw_paths is None
            else _string_tuple(raw_paths, key="paths")
        ),
        rules=_parse_rules(tool_config.get("forbidden", {})),
    )


def _resolved_paths(values: Sequence[str], base_dir: Path) -> tuple[Path, ...]:
    return tuple(
        (Path(value) if Path(value).is_absolute() else base_dir / value)
        for value in values
    )


def _violation_payload(violation: ImportViolation) -> dict[str, object]:
    return {
        "source_file": str(violation.source_file),
        "line": violation.line,
        "module_name": violation.module_name,
        "imported": violation.imported,
        "package": violation.package,
        "forbidden": violation.forbidden,
    }


def _print_report(
    violations: Sequence[ImportViolation],
    *,
    rules: Sequence[ImportRule],
    verbose: bool,
) -> int:
    print(f"import方向チェック: {len(rules)}規則を評価、違反 {len(violations)}件")
    if verbose:
        for rule in rules:
            print(f"情報: {rule.package} → 禁止 {', '.join(rule.forbidden)}")
    for violation in violations:
        print(f"違反: {violation.describe()}")
    if not violations:
        print("import方向の違反はありません。")
    return len(violations)


def main(argv: Sequence[str] | None = None) -> int:
    """CLIエントリーポイント。"""
    parser = argparse.ArgumentParser(description="import の依存方向を検証する。")
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
    parser.add_argument(
        "--verbose", action="store_true", help="評価した規則も表示する。"
    )
    parser.add_argument("--json", action="store_true", help="違反をJSONで出力する。")
    parser.add_argument(
        "--fail-on-violation",
        action="store_true",
        help="違反がある場合に終了コード1を返す。",
    )
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
        base_dir = args.config.parent.resolve()
        configured_paths = tuple(args.path) if args.path else config.paths
        paths = _resolved_paths(configured_paths, base_dir)
        root = _resolved_paths((config.root,), base_dir)[0]
        violations = analyze_paths(paths, root=root, rules=config.rules)
    except (ImportAnalysisError, OSError, ValueError) as error:
        print(f"import方向チェックに失敗しました: {error}", file=sys.stderr)
        return 2

    if args.json:
        print(
            json.dumps(
                [_violation_payload(violation) for violation in violations],
                ensure_ascii=False,
                indent=2,
            )
        )
        count = len(violations)
    else:
        count = _print_report(violations, rules=config.rules, verbose=args.verbose)
    return 1 if args.fail_on_violation and count else 0


if __name__ == "__main__":
    raise SystemExit(main())
