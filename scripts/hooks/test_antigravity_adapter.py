from __future__ import annotations

import json
import shlex
import subprocess
import sys
from pathlib import Path

from scripts.hooks import antigravity_adapter as adapter

ROOT = Path(__file__).resolve().parents[2]


def test_quality_post_tool_translates_edit_file(monkeypatch):
    captured_events = []

    def mock_quality_main(event):
        captured_events.append(event)
        return {}

    from scripts.hooks import quality_gate

    monkeypatch.setattr(quality_gate, "main", mock_quality_main)

    payload = {
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
    assert event["tool_input"]["file_path"] == "backend/test.py"
    assert event["turn_id"] == "conv-123"


def test_quality_post_tool_translates_replace_file_content_and_target_file(
    monkeypatch,
):
    captured_events = []

    def mock_quality_main(event):
        captured_events.append(event)
        return {}

    from scripts.hooks import quality_gate

    monkeypatch.setattr(quality_gate, "main", mock_quality_main)

    payload = {
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
    assert event["tool_input"]["file_path"] == "backend/app.py"


def test_quality_post_tool_translates_write_to_file(monkeypatch):
    captured_events = []

    def mock_quality_main(event):
        captured_events.append(event)
        return {}

    from scripts.hooks import quality_gate

    monkeypatch.setattr(quality_gate, "main", mock_quality_main)

    payload = {
        "toolCall": {
            "name": "write_to_file",
            "args": {"TargetFile": "scripts/sample.py", "Content": "# test"},
        },
        "stepIdx": 1,
    }

    result = adapter.handle_quality_post_tool(payload)
    assert result == {}
    assert len(captured_events) == 1
    assert captured_events[0]["tool_name"] == "Write"
    assert captured_events[0]["tool_input"]["file_path"] == "scripts/sample.py"
    assert captured_events[0]["turn_id"] == "current"


def test_quality_post_tool_feedback_is_delivered_once_on_pre_invocation(
    tmp_path, monkeypatch
):
    from scripts.hooks import quality_gate

    monkeypatch.setattr(adapter, "ROOT", tmp_path)
    feedback = iter(("Fix the type error.", "Preserve the edit-loop warning."))

    monkeypatch.setattr(
        quality_gate,
        "main",
        lambda event: {"hookSpecificOutput": {"additionalContext": next(feedback)}},
    )

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
                    "Quality gate feedback from the previous edit:\n"
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


def test_registered_hook_commands_resolve_from_workspace_root():
    hooks_path = ROOT / ".agents/hooks.json"
    data = json.loads(hooks_path.read_text(encoding="utf-8"))
    commands = [
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
            ROOT / "scripts/hooks/antigravity_adapter.py"
        ).resolve()


def test_privacy_post_tool_handles_run_command(monkeypatch):
    captured_events = []

    def mock_privacy_main(event):
        captured_events.append(event)
        return {}

    from scripts.hooks import privacy_gate

    monkeypatch.setattr(privacy_gate, "main", mock_privacy_main)

    payload = {
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


def test_privacy_stop_blocks_first_time_and_allows_stop_on_second_time(
    tmp_path, monkeypatch, capsys
):
    from scripts.hooks import privacy_gate

    monkeypatch.setattr(adapter, "ROOT", tmp_path)

    def mock_privacy(event):
        if event.get("stop_hook_active"):
            return {
                "systemMessage": "Privacy finding unresolved. Report findings; do not claim success."
            }
        return {
            "decision": "block",
            "reason": "Personal user path detected in sample.py:1",
        }

    monkeypatch.setattr(privacy_gate, "main", mock_privacy)

    payload = {
        "executionNum": 1,
        "terminationReason": "NO_TOOL_CALL",
        "conversationId": "bounded-privacy-turn",
    }

    first_result = adapter.handle_privacy_stop(payload)
    assert first_result["decision"] == "continue"
    assert "Personal user path detected" in first_result["reason"]

    second_result = adapter.handle_privacy_stop(payload)
    assert second_result == {}
    captured = capsys.readouterr()
    assert "[PRIVACY GATE WARNING] Privacy finding unresolved" in captured.err


def test_privacy_stop_allows_when_passing(tmp_path, monkeypatch):
    from scripts.hooks import privacy_gate

    monkeypatch.setattr(adapter, "ROOT", tmp_path)
    monkeypatch.setattr(privacy_gate, "main", lambda event: {})

    payload = {
        "executionNum": 1,
        "terminationReason": "NO_TOOL_CALL",
        "conversationId": "turn-clean",
    }
    result = adapter.handle_privacy_stop(payload)
    assert result == {}


def test_quality_stop_translates_quality_block_to_continue(monkeypatch):
    from scripts.hooks import quality_gate

    monkeypatch.setattr(
        quality_gate,
        "main",
        lambda event: {
            "decision": "block",
            "reason": "Quality checks failed: mypy error",
        },
    )

    payload = {
        "executionNum": 2,
        "terminationReason": "NO_TOOL_CALL",
        "conversationId": "turn-99",
    }
    result = adapter.handle_quality_stop(payload)
    assert result["decision"] == "continue"
    assert "Quality checks failed: mypy error" in result["reason"]


def test_quality_stop_allows_stopping_when_passing(monkeypatch):
    from scripts.hooks import quality_gate

    monkeypatch.setattr(quality_gate, "main", lambda event: {})

    payload = {
        "executionNum": 3,
        "terminationReason": "NO_TOOL_CALL",
        "conversationId": "turn-99",
    }
    result = adapter.handle_quality_stop(payload)
    assert result == {}


def test_quality_stop_delivers_terminal_failure_warning(monkeypatch, capsys):
    from scripts.hooks import quality_gate

    monkeypatch.setattr(
        quality_gate,
        "main",
        lambda event: {
            "systemMessage": "Quality repair stopped: stagnated. Unresolved failures remain."
        },
    )

    payload = {"executionNum": 4, "terminationReason": "NO_TOOL_CALL"}
    result = adapter.handle_quality_stop(payload)
    assert result == {}
    captured = capsys.readouterr()
    assert "[QUALITY GATE WARNING] Quality repair stopped: stagnated" in captured.err


def test_registered_antigravity_hooks_json_matches_codex_coverage():
    hooks_path = ROOT / ".agents/hooks.json"
    assert hooks_path.exists(), ".agents/hooks.json must exist"
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


def test_cli_launcher_granular_actions():
    for action in (
        "quality-post-tool",
        "quality-pre-invocation",
        "privacy-post-tool",
    ):
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/hooks/antigravity_adapter.py"),
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
