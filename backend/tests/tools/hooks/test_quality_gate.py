"""品質ゲートおよび修復状態管理の単体テスト。"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.hooks.format_edited_python import edited_files
from tools.hooks.quality_feedback import repair_state, report_feedback
from tools.hooks.quality_gate import changed_paths, fingerprint, stop_decision


def test_修復状態_進捗と未知の失敗および成功を区別する() -> None:
    state = repair_state(None, 1, "A+B")
    state = repair_state(state, 1, "A")
    assert state["repeated_failures"] == 1
    state = repair_state(state, 1, "B")
    assert state["repeated_failures"] == 1
    state = repair_state(state, 0, None)
    assert state["attempts"] == 0
    assert repair_state(state, 1, "B")["repeated_failures"] == 1
    for _ in range(6):
        state = repair_state(state, 1, None)
    assert state["terminal"] == "attempt_limit"
    assert state["repeated_failures"] == 0
    assert report_feedback({"tasks": [{"status": "failed"}]})[0] is None


@pytest.fixture
def stop_context(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    from tools.hooks import quality_gate as gate

    context = ["head-and-settings-v1"]
    monkeypatch.setattr(gate, "validation_context", lambda root: context[0])
    return context


def test_修復状態_同一診断結果の場合はソース変更があっても修復を停止する(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stop_context: list[str]
) -> None:
    from tools.hooks import quality_gate as gate

    source = tmp_path / "changed.py"
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    monkeypatch.setattr(gate, "changed_paths", lambda root: ["changed.py"])
    calls: list[object] = []

    def execute(command: list[str], **kwargs: object) -> SimpleNamespace:
        calls.append(command)
        report_path = command[command.index("--report") + 1]
        Path(report_path).write_text(
            json.dumps(
                {
                    "tasks": [
                        {
                            "label": "Acceptance R1",
                            "status": "failed",
                            "feedback": {
                                "identity": "same-failing-test-and-error",
                                "diagnostics": ["test_access"],
                                "suggestion": "認可分岐を修正してください",
                                "docs": "docs/development.md",
                            },
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        return SimpleNamespace(returncode=1)

    monkeypatch.setattr(subprocess, "run", execute)
    event: dict[str, object] = {
        "hook_event_name": "Stop",
        "turn_id": "repair-task",
        "stop_hook_active": True,
    }
    for attempt in range(3):
        source.write_text(f"# distinct implementation {attempt}", encoding="utf-8")
        decision = gate.main(event)
        if attempt < 2:
            assert decision["decision"] == "block"
            assert "認可分岐を修正してください" in str(decision["reason"])
        else:
            assert "decision" not in decision
            assert "stagnated" in str(decision["systemMessage"])
            assert "成功を主張" in str(decision["systemMessage"])
    assert gate.main(event)["systemMessage"]
    assert len(calls) == 3
    receipt = next(
        path
        for path in (tmp_path / ".agents/work/.hooks").glob("*.json")
        if ".report." not in path.name
    )
    state = json.loads(receipt.read_text(encoding="utf-8"))
    assert state["result"] != 0
    assert state["repeated_failures"] == 3


def test_タスク仕様変更時_Stopの成功レシートを無効化する(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stop_context: list[str]
) -> None:
    from tools.hooks import quality_gate as gate

    monkeypatch.setattr(gate, "ROOT", tmp_path)
    monkeypatch.setattr(gate, "changed_paths", lambda root: [])
    calls: list[object] = []

    def execute(*args: object, **kwargs: object) -> SimpleNamespace:
        calls.append(args)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(subprocess, "run", execute)
    event: dict[str, object] = {"hook_event_name": "Stop"}
    assert gate.main(event) == {}
    spec = tmp_path / "tmp/quality/task.json"
    spec.parent.mkdir(parents=True)
    spec.write_text('{"version":1}', encoding="utf-8")
    assert gate.main(event) == {}
    assert len(calls) == 2


@pytest.mark.parametrize("status", ["timeout", "start_error"])
def test_ランナーインフラ障害時_レシートに失敗状態が記録される(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stop_context: list[str],
    status: str,
) -> None:
    from tools.hooks import quality_gate as gate

    monkeypatch.setattr(gate, "ROOT", tmp_path)
    monkeypatch.setattr(gate, "changed_paths", lambda root: [])

    directory = tmp_path / ".agents/work/.hooks"
    directory.mkdir(parents=True)
    key = hashlib.sha256(b"current").hexdigest()[:24]
    (directory / f"{key}.report.json").write_text('{"status": "passed"}')

    def execute(*args: object, **kwargs: object) -> SimpleNamespace:
        if status == "timeout":
            raise subprocess.TimeoutExpired("node", 540)
        raise FileNotFoundError("node unavailable")

    monkeypatch.setattr(subprocess, "run", execute)
    assert gate.main({"hook_event_name": "Stop"})["decision"] == "block"
    receipt = json.loads(
        next((tmp_path / ".agents/work/.hooks").glob("*.json")).read_text()
    )
    assert receipt["status"] == status
    assert receipt["result"] != 0
    assert receipt["report"] is None
    assert (tmp_path / ".agents/work/.hooks" / receipt["log"]).is_file()


def test_検査失敗時_一度だけ継続を許可するが成功は主張しない() -> None:
    assert stop_decision({}, "a", None, 1)["decision"] == "block"
    previous: dict[str, object] = {"signature": "a", "result": 1}
    decision = stop_decision({"stop_hook_active": True}, "a", previous, None)
    assert "decision" not in decision
    assert "依然として失敗" in str(decision["systemMessage"])
    assert stop_decision({}, "b", previous, 1)["decision"] == "block"
    assert stop_decision({}, "a", {"signature": "a", "result": 0}, None) == {}


def test_フィンガープリント_変更および削除されたファイル内容を正しく検知する(
    tmp_path: Path,
) -> None:
    file = tmp_path / "a.py"
    file.write_text("one", encoding="utf-8")
    first = fingerprint(tmp_path, ["a.py"])
    file.write_text("two", encoding="utf-8")
    second = fingerprint(tmp_path, ["a.py"])
    file.unlink()
    assert len({first, second, fingerprint(tmp_path, ["a.py"])}) == 3


def test_検証コンテキスト_HEADとクリーンな設定ファイルを追跡する(
    tmp_path: Path,
) -> None:
    from tools.hooks.quality_gate import validation_context

    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    def commit() -> None:
        git("add", ".")
        git(
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "--no-verify",
            "--allow-empty",
            "-m",
            "fixture",
        )

    git("init")
    configuration = tmp_path / "pytest.ini"
    configuration.write_text("[pytest]\n", encoding="utf-8")
    commit()
    original = validation_context(tmp_path)
    assert validation_context(tmp_path) == original
    configuration.write_text("[pytest]\naddopts = -q\n", encoding="utf-8")
    assert validation_context(tmp_path) != original
    configuration.write_text("[pytest]\n", encoding="utf-8")
    assert validation_context(tmp_path) == original
    commit()
    assert validation_context(tmp_path) != original


def test_検証中の設定変更時_成功をブロックする(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stop_context: list[str]
) -> None:
    from tools.hooks import quality_gate as gate

    monkeypatch.setattr(gate, "ROOT", tmp_path)
    monkeypatch.setattr(gate, "changed_paths", lambda root: [])

    def execute(*args: object, **kwargs: object) -> SimpleNamespace:
        stop_context[0] = "changed-configuration"
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(subprocess, "run", execute)
    assert gate.main({"hook_event_name": "Stop"})["decision"] == "block"


def test_変更パス取得_ステージ_未ステージ_削除_未追跡ファイルをすべて含む(
    tmp_path: Path,
) -> None:
    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init")
    for name in ("staged.py", "unstaged.py", "deleted.py"):
        (tmp_path / name).write_text("before", encoding="utf-8")
    git("add", ".")
    git(
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "--no-verify",
        "-m",
        "test: fixture",
    )
    (tmp_path / "staged.py").write_text("after", encoding="utf-8")
    git("add", "staged.py")
    (tmp_path / "unstaged.py").write_text("after", encoding="utf-8")
    (tmp_path / "deleted.py").unlink()
    (tmp_path / "untracked.py").write_text("new", encoding="utf-8")
    assert changed_paths(tmp_path) == [
        "deleted.py",
        "staged.py",
        "unstaged.py",
        "untracked.py",
    ]


def test_パッチ文字列および構造化入力_編集ファイルパスを正しく解釈する() -> None:
    from tools.hooks.format_edited_python import ROOT

    file = ROOT / "backend/tools/hooks/quality_gate.py"
    patch = f"*** Update File: {file.as_posix()}\n"
    for payload in (patch, {"command": patch}, {"patch": patch}):
        assert edited_files({"tool_name": "apply_patch", "tool_input": payload}) == [
            file
        ]
    assert (
        edited_files(
            {"tool_name": "Write", "tool_input": {"file_path": "../outside.py"}}
        )
        == []
    )


def test_Stop判定_検査を実行し現在の成功結果のみを再利用する(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stop_context: list[str]
) -> None:
    from tools.hooks import quality_gate as gate

    source = tmp_path / "changed.py"
    source.write_text("before", encoding="utf-8")
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    monkeypatch.setattr(gate, "changed_paths", lambda root: ["changed.py"])
    calls: list[object] = []

    def execute(*args: object, **kwargs: object) -> SimpleNamespace:
        calls.append(args)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(subprocess, "run", execute)
    event: dict[str, object] = {"hook_event_name": "Stop", "turn_id": "test-turn"}
    assert gate.main(event) == {}
    assert gate.main(event) == {}
    assert len(calls) == 1
    call_args = calls[0]
    assert isinstance(call_args, tuple) and "--require-spec" in call_args[0]
    source.write_text("after", encoding="utf-8")
    assert gate.main(event) == {}
    assert len(calls) == 2
    stop_context[0] = "head-and-settings-v2"
    assert gate.main(event) == {}
    assert len(calls) == 3
    receipt = next((tmp_path / ".agents/work/.hooks").glob("*.json"))
    receipt.write_text("broken json", encoding="utf-8")
    assert gate.main(event) == {}
    assert len(calls) == 4


def test_検査実行中のファイル変更_成功レシートの発行を拒否する(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stop_context: list[str]
) -> None:
    from tools.hooks import quality_gate as gate

    source = tmp_path / "changed.py"
    source.write_text("before", encoding="utf-8")
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    monkeypatch.setattr(gate, "changed_paths", lambda root: ["changed.py"])

    def execute(*args: object, **kwargs: object) -> SimpleNamespace:
        source.write_text("changed during checks", encoding="utf-8")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(subprocess, "run", execute)
    assert (
        gate.main({"hook_event_name": "Stop", "turn_id": "test-turn"})["decision"]
        == "block"
    )


def test_ファイル編集後_クイック検査の前に自動フォーマットを実行する(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools.hooks import quality_gate as gate

    order: list[str] = []
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    monkeypatch.setattr(
        gate, "edited_paths", lambda event: [gate.ROOT / "backend/app/main.py"]
    )

    def format_event(event: dict[str, object]) -> int:
        order.append("format")
        return 0

    monkeypatch.setattr(gate, "format_python", format_event)
    calls: list[object] = []

    def execute(*args: object, **kwargs: object) -> SimpleNamespace:
        order.append("check")
        calls.append(args)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(subprocess, "run", execute)
    assert gate.main({"hook_event_name": "PostToolUse"}) == {}
    assert order == ["format", "check"]
    call_args = calls[0]
    assert isinstance(call_args, tuple) and "--require-spec" in call_args[0]


def test_ファイル編集後_型エラー発生時はStopをブロックする(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stop_context: list[str]
) -> None:
    from tools.hooks import quality_gate as gate

    source = tmp_path / "backend/app/main.py"
    source.parent.mkdir(parents=True)
    source.write_text("# test fixture", encoding="utf-8")
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    monkeypatch.setattr(gate, "edited_paths", lambda event: [source])
    monkeypatch.setattr(gate, "format_python", lambda event: 0)
    monkeypatch.setattr(gate, "changed_paths", lambda root: ["backend/app/main.py"])

    def execute(*args: object, **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(
            returncode=1,
            stdout=b'main.py:1: error: Argument "database_schema" has incompatible type "str | None"; expected "str" [arg-type]',
            stderr=b"",
        )

    monkeypatch.setattr(subprocess, "run", execute)
    result = gate.main({"hook_event_name": "PostToolUse"})
    raw_output = result.get("hookSpecificOutput")
    assert isinstance(raw_output, dict)
    assert "[arg-type]" in str(raw_output.get("additionalContext"))
    assert gate.main({"hook_event_name": "Stop"})["decision"] == "block"


def test_ファイル編集後_同一ファイル5回編集時に一度だけ警告する(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools.hooks import quality_gate as gate

    source = tmp_path / "backend/app/main.py"
    source.parent.mkdir(parents=True)
    source.write_text("# fixture", encoding="utf-8")
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    monkeypatch.setattr(gate, "edited_paths", lambda event: [source])
    monkeypatch.setattr(gate, "format_python", lambda event: 0)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=b"", stderr=b""),
    )
    event: dict[str, object] = {
        "hook_event_name": "PostToolUse",
        "turn_id": "edit-loop-turn",
    }

    results = [gate.main(event) for _ in range(6)]

    assert all("decision" not in result for result in results)
    raw_output = results[4].get("hookSpecificOutput")
    assert isinstance(raw_output, dict)
    warning = str(raw_output.get("additionalContext"))
    assert "backend/app/main.py" in warning
    assert "5回" in warning
    assert "見直" in warning
    assert results[5] == {}


def test_ファイル編集後_ターンごとにファイル別カウントを追跡し秘密情報を漏洩しない(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools.hooks import quality_gate as gate

    first = tmp_path / "backend/app/main.py"
    second = tmp_path / "scripts/checks/quality.mjs"
    first.parent.mkdir(parents=True)
    second.parent.mkdir(parents=True)
    first.write_text("private source contents", encoding="utf-8")
    second.write_text("private source contents", encoding="utf-8")
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    monkeypatch.setattr(gate, "edited_paths", lambda event: [first, first, second])
    monkeypatch.setattr(gate, "format_python", lambda event: 0)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=b"", stderr=b""),
    )

    first_turn: dict[str, object] = {
        "hook_event_name": "PostToolUse",
        "turn_id": "first-turn",
    }
    second_turn: dict[str, object] = {
        "hook_event_name": "PostToolUse",
        "turn_id": "second-turn",
    }
    first_turn_results = [gate.main(first_turn) for _ in range(4)]
    second_turn_results = [gate.main(second_turn) for _ in range(5)]

    assert first_turn_results == [{}] * 4
    assert second_turn_results[:4] == [{}] * 4
    raw_output = second_turn_results[4].get("hookSpecificOutput")
    assert isinstance(raw_output, dict)
    warning = str(raw_output.get("additionalContext"))
    assert "backend/app/main.py" in warning
    assert "scripts/checks/quality.mjs" in warning

    states = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in (tmp_path / ".agents/work/.hooks").glob("*.edits.json")
    ]
    assert len(states) == 2
    assert all(
        set(state["counts"]) == {"backend/app/main.py", "scripts/checks/quality.mjs"}
        for state in states
    )
    assert sorted(state["counts"]["backend/app/main.py"] for state in states) == [4, 5]
    assert sorted(
        state["counts"]["scripts/checks/quality.mjs"] for state in states
    ) == [4, 5]
    serialized = " ".join(
        path.read_text(encoding="utf-8")
        for path in (tmp_path / ".agents/work/.hooks").glob("*.edits.json")
    )
    assert str(tmp_path) not in serialized
    assert "private source contents" not in serialized


def test_編集カウント_ブロックされたStopを生き残り許可されたStop後にクリアされる(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stop_context: list[str]
) -> None:
    from tools.hooks import quality_gate as gate

    source = tmp_path / "backend/app/main.py"
    source.parent.mkdir(parents=True)
    source.write_text("# fixture", encoding="utf-8")
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    monkeypatch.setattr(gate, "edited_paths", lambda event: [source])
    monkeypatch.setattr(gate, "format_python", lambda event: 0)
    monkeypatch.setattr(gate, "changed_paths", lambda root: [])
    stop_state = {"running": False, "exit_code": 1}

    def execute(*args: object, **kwargs: object) -> SimpleNamespace:
        if stop_state["running"]:
            return SimpleNamespace(returncode=stop_state["exit_code"])
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(subprocess, "run", execute)
    edit_event: dict[str, object] = {
        "hook_event_name": "PostToolUse",
        "turn_id": "stop-lifetime",
    }
    stop_event: dict[str, object] = {
        "hook_event_name": "Stop",
        "turn_id": "stop-lifetime",
    }

    for _ in range(4):
        assert gate.main(edit_event) == {}
    state_path = next((tmp_path / ".agents/work/.hooks").glob("*.edits.json"))

    stop_state["running"] = True
    assert gate.main(stop_event)["decision"] == "block"
    assert state_path.is_file()
    stop_state["running"] = False
    raw_output = gate.main(edit_event).get("hookSpecificOutput")
    assert isinstance(raw_output, dict)
    warning = str(raw_output.get("additionalContext"))
    assert "5回" in warning

    stop_state["running"] = True
    stop_state["exit_code"] = 0
    assert gate.main(stop_event) == {}
    assert not state_path.exists()


def test_mypy設定_Optional引数の型不整合を検出できる(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[4]
    source = tmp_path / "schema_probe.py"
    source.write_text(
        "def create_app_lifespan(*, database_schema: str) -> None:\n"
        "    pass\n"
        "def configure(schema: str | None) -> None:\n"
        "    create_app_lifespan(database_schema=schema)\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mypy",
            "--config-file",
            "backend/pyproject.toml",
            "--no-incremental",
            str(source),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "[arg-type]" in result.stdout
    assert '"str | None"' in result.stdout
