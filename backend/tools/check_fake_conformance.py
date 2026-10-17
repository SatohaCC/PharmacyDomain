"""テストダブルが Protocol の全メンバを上書きしているか検証する静的解析ツール。

`class Fake(SomeProtocol)` のように Protocol を明示継承すると、上書きし忘れた
メンバは Protocol 本体の `...` を実装として継承する。呼び出しても例外にならず
`None` が返るため、Protocol 側のメンバを改名・追加したときにフェイクが
「静かに壊れる」。mypy は抽象メンバの未実装として検出できるが、pytest ほど
頻繁には走らない。このチェッカは同じ検出を pytest 側へ持ち込む。

`...` は AST だけでは Protocol の継承関係とメンバ集合まで解決できないため、
`tools/check_imports.py` と異なり対象モジュールを import して検査する。
"""

from __future__ import annotations

import argparse
import importlib
import inspect
import sys
import tomllib
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PATHS = ("tests/fakes",)


class FakeConformanceError(Exception):
    """フェイク適合性の解析に失敗した場合の例外。"""


@dataclass(frozen=True, slots=True)
class FakeRulesConfig:
    """フェイク適合性チェックの設定。"""

    root: str = "."
    paths: tuple[str, ...] = DEFAULT_PATHS


@dataclass(frozen=True, slots=True)
class Violation:
    """1件の未実装メンバ。"""

    module_name: str
    class_name: str
    protocol_name: str
    member_name: str

    def describe(self) -> str:
        """違反内容を1行で説明する。"""
        return (
            f"{self.module_name}.{self.class_name} が "
            f"{self.protocol_name}.{self.member_name} を上書きしていません"
            "（Protocol本体の ... を継承するため、呼ぶと None が返ります）。"
        )


def _string_tuple(value: object, *, key: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"[tool.fake_rules].{key} は文字列の配列で指定してください。")
    return tuple(value)


def load_config(config_path: Path = Path("pyproject.toml")) -> FakeRulesConfig:
    """pyproject.tomlからフェイク適合性設定を読み込む。"""
    if not config_path.exists():
        return FakeRulesConfig()

    with config_path.open("rb") as file:
        document = tomllib.load(file)
    tool_config = document.get("tool", {}).get("fake_rules", {})
    if not isinstance(tool_config, dict):
        raise ValueError("[tool.fake_rules] はテーブルとして指定してください。")

    raw_root = tool_config.get("root", ".")
    if not isinstance(raw_root, str):
        raise ValueError("[tool.fake_rules].root は文字列で指定してください。")
    raw_paths = tool_config.get("paths")
    return FakeRulesConfig(
        root=raw_root,
        paths=(
            DEFAULT_PATHS
            if raw_paths is None
            else _string_tuple(raw_paths, key="paths")
        ),
    )


def _module_name_for(source_file: Path, root: Path) -> str:
    relative = source_file.resolve().relative_to(root)
    parts = relative.with_suffix("").parts
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _iter_module_names(target: Path, root: Path) -> Iterator[str]:
    """検査対象のモジュール名を列挙する。"""
    if target.is_file():
        yield _module_name_for(target, root)
        return
    if not target.is_dir():
        raise FakeConformanceError(f"検査対象が存在しません: {target}")
    for source_file in sorted(target.rglob("*.py")):
        if "__pycache__" in source_file.parts:
            continue
        yield _module_name_for(source_file, root)


def _protocol_bases(cls: type[object]) -> tuple[type[object], ...]:
    """明示継承している Protocol を、自身を除く MRO から集める。"""
    return tuple(
        base for base in cls.__mro__[1:] if getattr(base, "_is_protocol", False)
    )


def _protocol_members(protocol: type[object]) -> tuple[str, ...]:
    """Protocol が要求するメンバ名を返す。"""
    declared = getattr(protocol, "__protocol_attrs__", None)
    if declared is not None:
        members = set(declared)
    else:
        members = {
            name
            for name, value in vars(protocol).items()
            if callable(value) and not name.startswith("_")
        }
    return tuple(sorted(members))


def _is_overridden(cls: type[object], member_name: str) -> bool:
    """Protocol でない実装クラスがそのメンバを定義しているかを返す。"""
    return any(
        member_name in vars(owner)
        for owner in cls.__mro__
        if not getattr(owner, "_is_protocol", False)
    )


def analyze_module(module_name: str) -> tuple[Violation, ...]:
    """1モジュールを import し、未実装メンバを列挙する。"""
    try:
        module = importlib.import_module(module_name)
    except Exception as error:  # import 不能そのものが違反である
        raise FakeConformanceError(
            f"{module_name} を import できません: {type(error).__name__}: {error}"
        ) from error

    violations: list[Violation] = []
    for class_name, cls in vars(module).items():
        if not inspect.isclass(cls) or cls.__module__ != module_name:
            continue
        if getattr(cls, "_is_protocol", False):
            continue
        for protocol in _protocol_bases(cls):
            for member_name in _protocol_members(protocol):
                if _is_overridden(cls, member_name):
                    continue
                violations.append(
                    Violation(
                        module_name=module_name,
                        class_name=class_name,
                        protocol_name=protocol.__name__,
                        member_name=member_name,
                    )
                )
    return tuple(violations)


def analyze_paths(paths: Sequence[Path], root: Path) -> tuple[Violation, ...]:
    """設定された全パスを検査する。"""
    violations: list[Violation] = []
    for target in paths:
        for module_name in _iter_module_names(target, root):
            violations.extend(analyze_module(module_name))
    return tuple(violations)


def _resolved_paths(values: Sequence[str], base_dir: Path) -> tuple[Path, ...]:
    return tuple(
        (Path(value) if Path(value).is_absolute() else base_dir / value)
        for value in values
    )


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
        help="検査対象。指定時は設定ファイルのpathsを上書きする。",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="違反が無い場合も検査結果を表示する。"
    )
    parser.add_argument(
        "--fail-on-violation",
        action="store_true",
        help="違反がある場合に終了コード1を返す。",
    )
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
        base_dir = args.config.parent.resolve()
        root = (base_dir / config.root).resolve()
        configured_paths = tuple(args.path) if args.path else config.paths
        paths = _resolved_paths(configured_paths, base_dir)
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        violations = analyze_paths(paths, root)
    except (FakeConformanceError, OSError, ValueError) as error:
        print(f"フェイク適合性チェックに失敗しました: {error}", file=sys.stderr)
        return 2

    for violation in violations:
        print(violation.describe())
    if args.verbose and not violations:
        print("フェイクはすべて実装Protocolの全メンバを上書きしています。")
    return 1 if args.fail_on_violation and violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
