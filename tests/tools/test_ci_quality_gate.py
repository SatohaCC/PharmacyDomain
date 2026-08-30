"""CI が AGENTS.md の品質ゲートを全部実行していることを凍結する。

`tools/` のチェッカも集約の不変条件も、実行されて初めて仕組みになる。
CI からゲートが1つ静かに抜けても、残りが緑なら誰も気づけない。
そこでゲートの一覧をここに表として持ち、ワークフローと AGENTS.md の
両方がその表を満たしていることを pytest で要求する。

ゲートを増減させるときは、この表・`.github/workflows/`・AGENTS.md の
3つを揃えない限りテストが落ちる。
"""

from __future__ import annotations

from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW_DIR = _ROOT / ".github" / "workflows"
_AGENTS_MD = _ROOT / "AGENTS.md"

# AGENTS.md「コマンド & 品質ゲート」と一致させる。
REQUIRED_GATES: tuple[str, ...] = (
    "uv sync --locked",
    "uv run pytest -q",
    "uv run mypy app tests",
    "uv run ruff check .",
    "uv run ruff format --check .",
    "uv run pytest -m integration -q",
)

# ゲートが「実行されるが誰も見ない」状態にならないための最低限のトリガ。
REQUIRED_TRIGGERS = frozenset({"push", "pull_request"})
REQUIRED_PUSH_BRANCH = "main"


def _load_workflows() -> list[tuple[Path, object]]:
    """`.github/workflows/` 配下のワークフローを読み込む。"""
    paths = sorted({*_WORKFLOW_DIR.glob("*.yml"), *_WORKFLOW_DIR.glob("*.yaml")})
    return [(path, yaml.safe_load(path.read_text(encoding="utf-8"))) for path in paths]


def _collect_run_commands(node: object) -> list[str]:
    """文書のどこにあっても ``run:`` の値を集める。

    ジョブやステップの構成を変えても壊れないよう、階層を仮定せず再帰で拾う。
    コメントは ``yaml.safe_load`` の時点で落ちているため、
    「コメントに書いてあるだけ」を実行していると誤認する余地はない。
    """
    if isinstance(node, list):
        return [command for item in node for command in _collect_run_commands(item)]
    if not isinstance(node, dict):
        return []
    commands: list[str] = []
    for key, value in node.items():
        if key == "run" and isinstance(value, str):
            commands.append(value)
        else:
            commands.extend(_collect_run_commands(value))
    return commands


def _trigger_section(document: object) -> object:
    """``on:`` セクションを取り出す。

    YAML 1.1 では引用符の無い ``on`` が真偽値 ``True`` として読まれるため、
    文字列キーと真偽値キーの両方を見る。
    """
    if not isinstance(document, dict):
        return None
    if "on" in document:
        return document["on"]
    return document.get(True)


def _trigger_names(document: object) -> frozenset[str]:
    """ワークフローの起動条件の名前を集める。"""
    section = _trigger_section(document)
    if isinstance(section, dict):
        return frozenset(str(key) for key in section)
    if isinstance(section, list):
        return frozenset(str(item) for item in section)
    if isinstance(section, str):
        return frozenset({section})
    return frozenset()


def _push_branches(document: object) -> frozenset[str]:
    """``push`` トリガが対象にしているブランチを集める。

    ブランチ指定が無い場合は全ブランチが対象なので `main` を含むとみなす。
    """
    section = _trigger_section(document)
    if not isinstance(section, dict):
        return frozenset()
    push = section.get("push")
    if push is None:
        return frozenset({REQUIRED_PUSH_BRANCH})
    if not isinstance(push, dict) or "branches" not in push:
        return frozenset({REQUIRED_PUSH_BRANCH})
    branches = push["branches"]
    if isinstance(branches, list):
        return frozenset(str(item) for item in branches)
    return frozenset({str(branches)})


def _missing_gates(document: object) -> list[str]:
    """そのワークフローが実行していないゲートを返す。"""
    executed = "\n".join(_collect_run_commands(document))
    return [gate for gate in REQUIRED_GATES if gate not in executed]


def test_CIワークフロー_1件以上見つかる() -> None:
    """探索が壊れたときに、無検査で緑になるのを防ぐ。"""
    # Act
    workflows = _load_workflows()

    # Assert
    assert workflows, f"{_WORKFLOW_DIR} にワークフローが1件も無い"


def test_CIワークフロー_品質ゲートを全部実行するものがある() -> None:
    # Arrange
    workflows = _load_workflows()

    # Act
    missing_by_path = {
        path.name: _missing_gates(document) for path, document in workflows
    }

    # Assert
    assert any(not missing for missing in missing_by_path.values()), (
        f"品質ゲートを全部実行するワークフローが無い: 不足={missing_by_path}"
    )


def test_CIワークフロー_品質ゲートはpushとpull_requestで起動する() -> None:
    # Arrange
    gate_workflows = [
        (path, document)
        for path, document in _load_workflows()
        if not _missing_gates(document)
    ]

    # Act / Assert: 起動条件が外れると、実行されないゲートは仕組みでなくなる
    for path, document in gate_workflows:
        triggers = _trigger_names(document)
        assert triggers >= REQUIRED_TRIGGERS, (
            f"{path.name} の起動条件が不足している: {sorted(triggers)}"
        )
        assert REQUIRED_PUSH_BRANCH in _push_branches(document), (
            f"{path.name} の push トリガが {REQUIRED_PUSH_BRANCH} を対象にしていない"
        )


def test_品質ゲート_AGENTS_mdに全部記載されている() -> None:
    # Arrange
    documented = _AGENTS_MD.read_text(encoding="utf-8")

    # Act
    missing = [gate for gate in REQUIRED_GATES if gate not in documented]

    # Assert: CIだけが知っているゲートは、手元で回せないので存在しないのと同じ
    assert not missing, f"AGENTS.md に記載の無いゲートがある: {missing}"
