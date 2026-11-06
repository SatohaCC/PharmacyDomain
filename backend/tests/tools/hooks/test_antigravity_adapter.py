"""Antigravityライフサイクルアダプタの単体テスト。"""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from tools.hooks import antigravity_adapter as adapter

ROOT = Path(__file__).resolve().parents[4]


def test_アダプタ_edit_file呼び出し時_Editツール形式のPostToolUseイベントへ変換する(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_events: list[dict[str, object]] = []

    def mock_quality_main(event: dict[str, object]) -> dict[str, object]:
        captured_events.append(event)
        return {}

    from tools.hooks import quality_gate

    monkeypatch.setattr(quality_gate, "main", mock_quality_main)

    payload: dict[str, object] = {
        "toolCall": {
            "name": "edit_file",
            "args": {"Path": "backend/test.py", "Target": "a", "Replacement": "b"},
        },
        "stepIdx": 2,
        "conversationId": "conv-123",
    }

    result = adapter.handle_quality_post_tool(payload)
    assert result == {}
    assert len(captured_events) == 1
    event = captured_events[0]
    assert event["hook_event_name"] == "PostToolUse"
    assert event["tool_name"] == "Edit"
    raw_input = event.get("tool_input")
    assert isinstance(raw_input, dict)
    assert raw_input.get("file_path") == "backend/test.py"
    assert event["turn_id"] == "conv-123"


def test_アダプタ_replace_file_content呼び出し時_Editツール形式のPostToolUseイベントへ変換する(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_events: list[dict[str, object]] = []

    def mock_quality_main(event: dict[str, object]) -> dict[str, object]:
        captured_events.append(event)
        return {}

    from tools.hooks import quality_gate

    monkeypatch.setattr(quality_gate, "main", mock_quality_main)

    payload: dict[str, object] = {
        "toolCall": {
            "name": "replace_file_content",
            "args": {
                "TargetFile": "backend/app.py",
                "OldContent": "x",
                "NewContent": "y",
            },
        },
        "stepIdx": 3,
        "conversationId": "conv-456",
    }

    result = adapter.handle_quality_post_tool(payload)
    assert result == {}
    assert len(captured_events) == 1
    event = captured_events[0]
    assert event["tool_name"] == "Edit"
    raw_input = event.get("tool_input")
    assert isinstance(raw_input, dict)
    assert raw_input.get("file_path") == "backend/app.py"


def test_アダプタ_write_to_file呼び出し時_Writeツール形式のPostToolUseイベントへ変換する(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_events: list[dict[str, object]] = []

    def mock_quality_main(event: dict[str, object]) -> dict[str, object]:
        captured_events.append(event)
        return {}

    from tools.hooks import quality_gate

    monkeypatch.setattr(quality_gate, "main", mock_quality_main)

    payload: dict[str, object] = {
        "toolCall": {
            "name": "write_to_file",
            "args": {"TargetFile": "backend/sample.py", "Content": "# test"},
        },
        "stepIdx": 1,
    }

    result = adapter.handle_quality_post_tool(payload)
    assert result == {}
    assert len(captured_events) == 1
    assert captured_events[0]["tool_name"] == "Write"
    raw_input = captured_events[0].get("tool_input")
    assert isinstance(raw_input, dict)
    assert raw_input.get("file_path") == "backend/sample.py"
    assert captured_events[0]["turn_id"] == "current"


def test_アダプタ_PreInvocation受信時_未配信の品質フィードバックを一度だけ注入する(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools.hooks import quality_gate

    monkeypatch.setattr(adapter, "ROOT", tmp_path)
    feedback = iter(("Fix the type error.", "Preserve the edit-loop warning."))

    def mock_gate(event: dict[str, object]) -> dict[str, object]:
        return {"hookSpecificOutput": {"additionalContext": next(feedback)}}

    monkeypatch.setattr(quality_gate, "main", mock_gate)

    for step_idx in (11, 12):
        result = adapter.handle_quality_post_tool(
            {
                "toolCall": {
                    "name": "replace_file_content",
                    "args": {"TargetFile": "backend/app.py"},
                },
                "stepIdx": step_idx,
                "conversationId": "quality-feedback-turn",
            }
        )
        assert result == {}

    expected = {
        "injectSteps": [
            {
                "ephemeralMessage": (
                    "前回の編集に対する品質ゲートフィードバック:\n"
                    "Fix the type error.\n\nPreserve the edit-loop warning."
                )
            }
        ]
    }
    assert (
        adapter.handle_quality_pre_invocation(
            {"conversationId": "quality-feedback-turn"}
        )
        == expected
    )
    assert (
        adapter.handle_quality_pre_invocation(
            {"conversationId": "quality-feedback-turn"}
        )
        == {}
    )


def test_アダプタ_登録済みフックコマンド_ワークスペースルートから解決可能である() -> (
    None
):
    hooks_path = ROOT / ".agents/hooks.json"
    data = json.loads(hooks_path.read_text(encoding="utf-8"))
    commands: list[str] = [
        hook["command"]
        for group in data.values()
        for handlers in group.values()
        for handler in handlers
        for hook in handler.get("hooks", [handler])
    ]

    assert commands
    assert all("../" not in command for command in commands)
    for command in commands:
        tokens = shlex.split(command)
        project_path = Path(tokens[tokens.index("--project") + 1])
        adapter_path = Path(tokens[tokens.index("python") + 1])
        assert (ROOT / project_path).resolve() == (ROOT / "backend").resolve()
        assert (ROOT / adapter_path).resolve() == (
            ROOT / "backend/tools/hooks/antigravity_adapter.py"
        ).resolve()


def test_アダプタ_run_command呼び出し時_プライバシー検査を呼び出す(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_events: list[dict[str, object]] = []

    def mock_privacy_main(event: dict[str, object]) -> dict[str, object]:
        captured_events.append(event)
        return {}

    from tools.hooks import privacy_gate

    monkeypatch.setattr(privacy_gate, "main", mock_privacy_main)

    payload: dict[str, object] = {
        "toolCall": {
            "name": "run_command",
            "args": {"CommandLine": "git status"},
        },
        "stepIdx": 1,
        "conversationId": "turn-bash",
    }

    result = adapter.handle_privacy_post_tool(payload)
    assert result == {}
    assert len(captured_events) == 1
    assert captured_events[0]["hook_event_name"] == "PostToolUse"
    assert captured_events[0]["tool_name"] == "Bash"
    assert captured_events[0]["turn_id"] == "turn-bash"


def test_アダプタ_プライバシー検査失敗時_初回は継続要求し2回目は停止を許可する(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from tools.hooks import privacy_gate

    monkeypatch.setattr(adapter, "ROOT", tmp_path)

    def mock_privacy(event: dict[str, object]) -> dict[str, object]:
        if event.get("stop_hook_active"):
            return {"systemMessage": "プライバシー指摘が未解決です。報告してください。"}
        return {
            "decision": "block",
            "reason": "個人パスが検出されました: sample.py:1",
        }

    monkeypatch.setattr(privacy_gate, "main", mock_privacy)

    payload: dict[str, object] = {
        "executionNum": 1,
        "terminationReason": "NO_TOOL_CALL",
        "conversationId": "bounded-privacy-turn",
    }

    first_result = adapter.handle_privacy_stop(payload)
    assert first_result["decision"] == "continue"
    assert "個人パスが検出されました" in str(first_result["reason"])

    second_result = adapter.handle_privacy_stop(payload)
    assert second_result == {}
    captured = capsys.readouterr()
    assert "[プライバシーゲート警告] プライバシー指摘が未解決です" in captured.err


def test_アダプタ_プライバシー検査成功時_正常に停止を許可する(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools.hooks import privacy_gate

    monkeypatch.setattr(adapter, "ROOT", tmp_path)
    monkeypatch.setattr(privacy_gate, "main", lambda event: {})

    payload: dict[str, object] = {
        "executionNum": 1,
        "terminationReason": "NO_TOOL_CALL",
        "conversationId": "turn-clean",
    }
    result = adapter.handle_privacy_stop(payload)
    assert result == {}


def test_アダプタ_品質検査ブロック時_継続要求へ変換する(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tools.hooks import quality_gate

    monkeypatch.setattr(
        quality_gate,
        "main",
        lambda event: {
            "decision": "block",
            "reason": "品質検査に失敗しました: mypy error",
        },
    )

    payload: dict[str, object] = {
        "executionNum": 2,
        "terminationReason": "NO_TOOL_CALL",
        "conversationId": "turn-99",
    }
    result = adapter.handle_quality_stop(payload)
    assert result["decision"] == "continue"
    assert "品質検査に失敗しました: mypy error" in str(result["reason"])


def test_アダプタ_品質検査成功時_正常に停止を許可する(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tools.hooks import quality_gate

    monkeypatch.setattr(quality_gate, "main", lambda event: {})

    payload: dict[str, object] = {
        "executionNum": 3,
        "terminationReason": "NO_TOOL_CALL",
        "conversationId": "turn-99",
    }
    result = adapter.handle_quality_stop(payload)
    assert result == {}


def test_アダプタ_停滞時_システム警告を出力する(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from tools.hooks import quality_gate

    monkeypatch.setattr(
        quality_gate,
        "main",
        lambda event: {
            "systemMessage": "品質修復を停止しました: stagnated。未解決の失敗が残っています。"
        },
    )

    payload: dict[str, object] = {
        "executionNum": 4,
        "terminationReason": "NO_TOOL_CALL",
    }
    result = adapter.handle_quality_stop(payload)
    assert result == {}
    captured = capsys.readouterr()
    assert "[品質ゲート警告] 品質修復を停止しました: stagnated" in captured.err


def test_アダプタ_登録済みAntigravityフック_Codexと一致するカバレッジを持つ() -> None:
    hooks_path = ROOT / ".agents/hooks.json"
    assert hooks_path.exists(), ".agents/hooks.json が存在する必要があります"
    data = json.loads(hooks_path.read_text(encoding="utf-8"))

    assert "quality-gate" in data
    assert "privacy-gate" in data

    q_gate = data["quality-gate"]
    assert "PostToolUse" in q_gate
    assert "PreInvocation" in q_gate
    assert "Stop" in q_gate
    q_matcher = q_gate["PostToolUse"][0]["matcher"]
    assert "replace_file_content" in q_matcher
    assert "write_to_file" in q_matcher
    assert "edit_file" in q_matcher
    assert q_gate["PostToolUse"][0]["hooks"][0]["timeout"] == 600
    pre_invocation_hook = q_gate["PreInvocation"][0]
    assert pre_invocation_hook["timeout"] == 30
    assert pre_invocation_hook["command"].endswith("quality-pre-invocation")
    assert q_gate["Stop"][0]["timeout"] == 600

    p_gate = data["privacy-gate"]
    assert "PostToolUse" in p_gate
    assert "Stop" in p_gate
    p_matcher = p_gate["PostToolUse"][0]["matcher"]
    assert "replace_file_content" in p_matcher
    assert "write_to_file" in p_matcher
    assert "run_command" in p_matcher
    assert p_gate["PostToolUse"][0]["hooks"][0]["timeout"] == 60
    assert p_gate["Stop"][0]["timeout"] == 60


def test_アダプタ_CLI起動時_サブコマンドを正しくディスパッチする() -> None:
    for action in (
        "quality-post-tool",
        "quality-pre-invocation",
        "privacy-post-tool",
    ):
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "backend/tools/hooks/antigravity_adapter.py"),
                action,
            ],
            cwd=ROOT,
            input=json.dumps({}),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert result.returncode == 0, f"{action} failed: {result.stderr}"
        assert json.loads(result.stdout) == {}
