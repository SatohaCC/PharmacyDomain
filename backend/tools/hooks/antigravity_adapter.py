"""Antigravityライフサイクルイベントを共通の品質・プライバシー検査ゲートへ接続する。"""

from __future__ import annotations

import contextlib
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def extract_file_path(args: dict[str, object]) -> str | None:
    """ツール引数から対象ファイルパスを抽出する。"""
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
    """各種エージェントのツール名をCodex形式の内部名へ正規化する。"""
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


def handle_quality_post_tool(payload: dict[str, object]) -> dict[str, object]:
    """PostToolUseイベントを受け取り、編集ファイルのクイック品質検査を実行する。"""
    raw_tool_call = payload.get("toolCall")
    tool_call: dict[str, object] = (
        raw_tool_call if isinstance(raw_tool_call, dict) else {}
    )
    raw_tool_name = str(tool_call.get("name", ""))
    raw_args = tool_call.get("args")
    args: dict[str, object] = raw_args if isinstance(raw_args, dict) else {}
    file_path = extract_file_path(args)
    codex_tool = normalize_tool_name(raw_tool_name)
    codex_event: dict[str, object] = {
        "hook_event_name": "PostToolUse",
        "tool_name": codex_tool,
        "tool_input": {"file_path": file_path} if file_path else args,
        "cwd": str(ROOT),
        "turn_id": str(payload.get("conversationId") or "current"),
    }
    from tools.hooks import quality_gate

    quality_decision = quality_gate.main(codex_event)
    raw_specific = quality_decision.get("hookSpecificOutput")
    specific = raw_specific if isinstance(raw_specific, dict) else {}
    additional_context = specific.get("additionalContext")
    if isinstance(additional_context, str) and additional_context.strip():
        queue_quality_feedback(
            str(payload.get("conversationId") or "current"),
            payload.get("stepIdx"),
            additional_context,
        )
    return {}


def handle_privacy_post_tool(payload: dict[str, object]) -> dict[str, object]:
    """PostToolUseイベントを受け取り、変更ファイルのプライバシー検査を実行する。"""
    raw_tool_call = payload.get("toolCall")
    tool_call: dict[str, object] = (
        raw_tool_call if isinstance(raw_tool_call, dict) else {}
    )
    raw_tool_name = str(tool_call.get("name", ""))
    raw_args = tool_call.get("args")
    args: dict[str, object] = raw_args if isinstance(raw_args, dict) else {}
    codex_tool = normalize_tool_name(raw_tool_name)
    codex_event: dict[str, object] = {
        "hook_event_name": "PostToolUse",
        "tool_name": codex_tool,
        "tool_input": args,
        "cwd": str(ROOT),
        "turn_id": str(payload.get("conversationId") or "current"),
    }
    from tools.hooks import privacy_gate

    decision = privacy_gate.main(codex_event)
    raw_specific = decision.get("hookSpecificOutput")
    specific = raw_specific if isinstance(raw_specific, dict) else {}
    if "additionalContext" in specific:
        print(specific["additionalContext"], file=sys.stderr)
    return {}


def quality_feedback_path(
    directory: Path, turn: str, step_idx: object, context: str
) -> Path:
    """フィードバックの一時保存先パスを生成する。"""
    turn_key = hashlib.sha256(turn.encode("utf-8")).hexdigest()[:24]
    if isinstance(step_idx, int) and step_idx >= 0:
        step_key = f"{step_idx:010d}"
    else:
        step_key = hashlib.sha256(context.encode("utf-8")).hexdigest()[:12]
    return directory / f"{turn_key}.{step_key}.quality-feedback.json"


def queue_quality_feedback(turn: str, step_idx: object, context: str) -> None:
    """次回Invocationのために品質フィードバックをキューへ保存する。"""
    directory = ROOT / ".agents/work/.hooks"
    directory.mkdir(parents=True, exist_ok=True)
    path = quality_feedback_path(directory, turn, step_idx, context)
    path.write_text(json.dumps(context, ensure_ascii=False), encoding="utf-8")


def take_quality_feedback(turn: str) -> list[str]:
    """保存された品質フィードバックを取り出し、一時ファイルを削除する。"""
    directory = ROOT / ".agents/work/.hooks"
    if not directory.is_dir():
        return []

    turn_key = hashlib.sha256(turn.encode("utf-8")).hexdigest()[:24]
    messages: list[str] = []
    for path in sorted(directory.glob(f"{turn_key}.*.quality-feedback.json")):
        try:
            context = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(context, str) and context.strip():
                messages.append(context)
        except ValueError, OSError:
            print(
                "無効な品質フィードバックレシートのため破棄しました。",
                file=sys.stderr,
            )
        finally:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                print(
                    "品質フィードバックレシートを削除できませんでした。",
                    file=sys.stderr,
                )
    return messages


def handle_quality_pre_invocation(payload: dict[str, object]) -> dict[str, object]:
    """PreInvocationイベントで前回ツールの品質フィードバックを注入する。"""
    turn_id = str(payload.get("conversationId") or "current")
    messages = take_quality_feedback(turn_id)
    if not messages:
        return {}
    return {
        "injectSteps": [
            {
                "ephemeralMessage": (
                    "前回の編集に対する品質ゲートフィードバック:\n"
                    + "\n\n".join(messages)
                )
            }
        ]
    }


def handle_quality_stop(payload: dict[str, object]) -> dict[str, object]:
    """Stopイベント時にフル品質検査を実行し、未完了時は継続を要求する。"""
    turn_id = str(
        payload.get("conversationId") or payload.get("executionNum") or "current"
    )
    codex_event: dict[str, object] = {
        "hook_event_name": "Stop",
        "turn_id": turn_id,
        "stop_hook_active": False,
    }
    from tools.hooks import quality_gate

    quality_decision = quality_gate.main(codex_event)
    if quality_decision.get("decision") == "block":
        return {
            "decision": "continue",
            "reason": str(quality_decision.get("reason", "品質検査に失敗しました。")),
        }

    if "systemMessage" in quality_decision:
        print(
            f"[品質ゲート警告] {quality_decision['systemMessage']}",
            file=sys.stderr,
        )

    return {}


def privacy_state_path(directory: Path, turn: str) -> Path:
    """プライバシー警告状態の一時ファイルパスを生成する。"""
    key = hashlib.sha256(turn.encode("utf-8")).hexdigest()[:24]
    return directory / f"{key}.privacy.json"


def handle_privacy_stop(payload: dict[str, object]) -> dict[str, object]:
    """Stopイベント時にプライバシー検査を実行する。"""
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
            if isinstance(stored, dict):
                already_warned = bool(stored.get("warned"))
    except ValueError, OSError:
        already_warned = False

    codex_event: dict[str, object] = {
        "hook_event_name": "Stop",
        "turn_id": turn_id,
        "stop_hook_active": already_warned,
    }
    from tools.hooks import privacy_gate

    privacy_decision = privacy_gate.main(codex_event)
    if privacy_decision.get("decision") == "block":
        with contextlib.suppress(OSError):
            state_file.write_text(json.dumps({"warned": True}), encoding="utf-8")
        return {
            "decision": "continue",
            "reason": str(
                privacy_decision.get("reason", "プライバシー検査に失敗しました。")
            ),
        }

    with contextlib.suppress(OSError):
        state_file.unlink(missing_ok=True)

    if "systemMessage" in privacy_decision:
        print(
            f"[プライバシーゲート警告] {privacy_decision['systemMessage']}",
            file=sys.stderr,
        )

    return {}


def main(action: str | None = None) -> dict[str, object]:
    """Antigravityライフサイクルイベントを適切なハンドラへ振り分ける。"""
    payload: dict[str, object]
    try:
        raw_input = sys.stdin.read()
        raw_json = json.loads(raw_input) if raw_input.strip() else {}
        payload = raw_json if isinstance(raw_json, dict) else {}
    except ValueError, OSError:
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
        print(f"Antigravityフック実行エラー: {error}", file=sys.stderr)
        print(json.dumps({}))
        raise SystemExit(1) from error
