"""Adapt Antigravity lifecycle events to shared quality and privacy checks."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def extract_file_path(args: dict) -> str | None:
    for key in (
        "TargetFile",
        "target_file",
        "FilePath",
        "file_path",
        "File",
        "file",
        "Path",
        "path",
    ):
        val = args.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def normalize_tool_name(tool_name: str) -> str:
    name = tool_name.rsplit(".", 1)[-1]
    if name in {
        "edit_file",
        "replace_file_content",
        "multi_replace_file_content",
        "Edit",
    }:
        return "Edit"
    if name in {"write_file", "write_to_file", "Write"}:
        return "Write"
    if name in {"run_command", "Bash", "exec_command"}:
        return "Bash"
    return name


def handle_quality_post_tool(payload: dict) -> dict:
    tool_call = payload.get("toolCall", {})
    raw_tool_name = tool_call.get("name", "")
    args = tool_call.get("args", {})
    file_path = extract_file_path(args)
    codex_tool = normalize_tool_name(raw_tool_name)
    codex_event = {
        "hook_event_name": "PostToolUse",
        "tool_name": codex_tool,
        "tool_input": {"file_path": file_path} if file_path else args,
        "cwd": str(ROOT),
        "turn_id": str(payload.get("conversationId") or "current"),
    }
    from scripts.hooks import quality_gate

    quality_decision = quality_gate.main(codex_event)
    additional_context = quality_decision.get("hookSpecificOutput", {}).get(
        "additionalContext"
    )
    if isinstance(additional_context, str) and additional_context.strip():
        queue_quality_feedback(
            str(payload.get("conversationId") or "current"),
            payload.get("stepIdx"),
            additional_context,
        )
    return {}


def handle_privacy_post_tool(payload: dict) -> dict:
    tool_call = payload.get("toolCall", {})
    raw_tool_name = tool_call.get("name", "")
    codex_tool = normalize_tool_name(raw_tool_name)
    codex_event = {
        "hook_event_name": "PostToolUse",
        "tool_name": codex_tool,
        "tool_input": tool_call.get("args", {}),
        "cwd": str(ROOT),
        "turn_id": str(payload.get("conversationId") or "current"),
    }
    from scripts.hooks import privacy_gate

    decision = privacy_gate.main(codex_event)
    if decision and "additionalContext" in decision.get("hookSpecificOutput", {}):
        print(decision["hookSpecificOutput"]["additionalContext"], file=sys.stderr)
    return {}


def quality_feedback_path(
    directory: Path, turn: str, step_idx: object, context: str
) -> Path:
    turn_key = hashlib.sha256(turn.encode("utf-8")).hexdigest()[:24]
    if type(step_idx) is int and step_idx >= 0:
        step_key = f"{step_idx:010d}"
    else:
        step_key = hashlib.sha256(context.encode("utf-8")).hexdigest()[:12]
    return directory / f"{turn_key}.{step_key}.quality-feedback.json"


def queue_quality_feedback(turn: str, step_idx: object, context: str) -> None:
    directory = ROOT / ".agents/work/.hooks"
    directory.mkdir(parents=True, exist_ok=True)
    path = quality_feedback_path(directory, turn, step_idx, context)
    path.write_text(json.dumps(context, ensure_ascii=False), encoding="utf-8")


def take_quality_feedback(turn: str) -> list[str]:
    directory = ROOT / ".agents/work/.hooks"
    if not directory.is_dir():
        return []

    turn_key = hashlib.sha256(turn.encode("utf-8")).hexdigest()[:24]
    messages = []
    for path in sorted(directory.glob(f"{turn_key}.*.quality-feedback.json")):
        try:
            context = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(context, str) and context.strip():
                messages.append(context)
        except (ValueError, OSError):
            print("Invalid quality feedback receipt; discarding it.", file=sys.stderr)
        finally:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                print("Could not clear quality feedback receipt.", file=sys.stderr)
    return messages


def handle_quality_pre_invocation(payload: dict) -> dict:
    turn_id = str(payload.get("conversationId") or "current")
    messages = take_quality_feedback(turn_id)
    if not messages:
        return {}
    return {
        "injectSteps": [
            {
                "ephemeralMessage": (
                    "Quality gate feedback from the previous edit:\n"
                    + "\n\n".join(messages)
                )
            }
        ]
    }


def handle_quality_stop(payload: dict) -> dict:
    turn_id = str(
        payload.get("conversationId") or payload.get("executionNum") or "current"
    )
    codex_event = {
        "hook_event_name": "Stop",
        "turn_id": turn_id,
        "stop_hook_active": False,
    }
    from scripts.hooks import quality_gate

    quality_decision = quality_gate.main(codex_event)
    if quality_decision.get("decision") == "block":
        return {
            "decision": "continue",
            "reason": quality_decision.get("reason", "Quality checks failed."),
        }

    if "systemMessage" in quality_decision:
        print(
            f"[QUALITY GATE WARNING] {quality_decision['systemMessage']}",
            file=sys.stderr,
        )

    return {}


def privacy_state_path(directory: Path, turn: str) -> Path:
    key = hashlib.sha256(turn.encode("utf-8")).hexdigest()[:24]
    return directory / f"{key}.privacy.json"


def handle_privacy_stop(payload: dict) -> dict:
    turn_id = str(
        payload.get("conversationId") or payload.get("executionNum") or "current"
    )
    directory = ROOT / ".agents/work/.hooks"
    directory.mkdir(parents=True, exist_ok=True)
    state_file = privacy_state_path(directory, turn_id)

    already_warned = False
    try:
        if state_file.exists():
            stored = json.loads(state_file.read_text(encoding="utf-8"))
            already_warned = bool(stored.get("warned"))
    except (ValueError, OSError):
        already_warned = False

    codex_event = {
        "hook_event_name": "Stop",
        "turn_id": turn_id,
        "stop_hook_active": already_warned,
    }
    from scripts.hooks import privacy_gate

    privacy_decision = privacy_gate.main(codex_event)
    if privacy_decision.get("decision") == "block":
        try:
            state_file.write_text(json.dumps({"warned": True}), encoding="utf-8")
        except OSError:
            pass
        return {
            "decision": "continue",
            "reason": privacy_decision.get("reason", "Privacy check failed."),
        }

    try:
        state_file.unlink(missing_ok=True)
    except OSError:
        pass

    if "systemMessage" in privacy_decision:
        print(
            f"[PRIVACY GATE WARNING] {privacy_decision['systemMessage']}",
            file=sys.stderr,
        )

    return {}


def main(action: str | None = None) -> dict:
    try:
        raw_input = sys.stdin.read()
        payload = json.loads(raw_input) if raw_input.strip() else {}
    except (ValueError, OSError):
        payload = {}

    if not action:
        if "toolCall" in payload:
            action = "post-tool-use"
        elif "terminationReason" in payload or "fullyIdle" in payload:
            action = "stop"
        else:
            action = "stop"

    if action in ("quality-post-tool",):
        return handle_quality_post_tool(payload)
    if action in ("quality-pre-invocation",):
        return handle_quality_pre_invocation(payload)
    if action in ("privacy-post-tool",):
        return handle_privacy_post_tool(payload)
    if action in ("quality-stop",):
        return handle_quality_stop(payload)
    if action in ("privacy-stop",):
        return handle_privacy_stop(payload)
    if action in ("post-tool-use", "PostToolUse"):
        handle_quality_post_tool(payload)
        handle_privacy_post_tool(payload)
        return {}
    if action in ("stop", "Stop"):
        privacy_res = handle_privacy_stop(payload)
        if privacy_res.get("decision") == "continue":
            return privacy_res
        return handle_quality_stop(payload)
    return {}


if __name__ == "__main__":
    event_arg = sys.argv[1] if len(sys.argv) > 1 else None
    try:
        result = main(event_arg)
        print(json.dumps(result, ensure_ascii=False))
    except Exception as error:
        print(f"Antigravity hook error: {error}", file=sys.stderr)
        print(json.dumps({}))
        raise SystemExit(1) from error
