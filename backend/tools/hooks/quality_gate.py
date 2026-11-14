"""CodexおよびAntigravityイベントを品質ランナーに接続し、Hook外で検査を実行する。"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from tools.hooks.format_edited_python import edited_paths  # noqa: E402
from tools.hooks.format_edited_python import main as format_python  # noqa: E402
from tools.hooks.quality_feedback import repair_state, report_feedback  # noqa: E402

EDIT_WARNING_THRESHOLD = 5


def changed_paths(root: Path) -> list[str]:
    """Git作業ツリー内の変更・未追跡ファイルパス一覧を返す。"""
    paths: set[str] = set()
    for args in (
        ["diff", "HEAD", "--name-only", "-z", "--no-renames"],
        ["ls-files", "--others", "--exclude-standard", "-z"],
    ):
        result = subprocess.run(
            ["git", *args], cwd=root, capture_output=True, check=True
        )
        paths.update(result.stdout.decode("utf-8").split("\0"))
    return sorted(path for path in paths if path)


def validation_context(root: Path) -> str:
    """レシートをHEADと追跡対象の検証設定に紐付ける。"""
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, check=True
    ).stdout
    tracked = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root, capture_output=True, check=True
    ).stdout.decode("utf-8")
    inputs = [
        name
        for name in tracked.split("\0")
        if name
        and (
            name.endswith((".json", ".toml", ".yaml", ".yml", ".ini", ".lock"))
            or name.startswith(("scripts/checks/", "backend/tools/hooks/"))
            or Path(name).name.startswith(
                (".python-version", ".nvmrc", ".importlinter")
            )
        )
    ]
    return head.decode("utf-8").strip() + ":" + fingerprint(root, inputs)


def fingerprint(root: Path, paths: list[str]) -> str:
    """指定パス群の内容ハッシュ（フィンガープリント）を計算する。"""
    digest = hashlib.sha256()
    for name in paths:
        digest.update(name.encode("utf-8") + b"\0")
        path = root / name
        if path.is_file():
            digest.update(path.read_bytes())
        else:
            digest.update(b"<deleted>")
        digest.update(b"\0")
    return digest.hexdigest()


def edit_state_path(directory: Path, turn: str) -> Path:
    """編集状態の一時保存パスを生成する。"""
    key = hashlib.sha256(turn.encode("utf-8")).hexdigest()[:24]
    return directory / f"{key}.edits.json"


def edit_loop_warnings(
    root: Path, event: dict[str, object], files: list[Path]
) -> list[str]:
    """同一ファイルの編集回数を追跡し、閾値を超えたファイル一覧を返す。"""
    if not files:
        return []

    turn = str(event.get("turn_id") or event.get("session_id") or "current")
    directory = root / ".agents/work/.hooks"
    state_path = edit_state_path(directory, turn)
    stored: dict[str, object]
    try:
        raw_json = json.loads(state_path.read_text(encoding="utf-8"))
        stored = raw_json if isinstance(raw_json, dict) else {}
    except OSError, ValueError:
        stored = {}
    if (
        not isinstance(stored, dict)
        or stored.get("version") != 1
        or not isinstance(stored.get("counts"), dict)
    ):
        stored = {}

    raw_counts = stored.get("counts")
    counts: dict[str, int] = (
        {
            str(name): int(count)
            for name, count in raw_counts.items()
            if isinstance(name, str) and isinstance(count, int) and count > 0
        }
        if isinstance(raw_counts, dict)
        else {}
    )
    raw_warned = stored.get("warned", [])
    stored_warned = raw_warned if isinstance(raw_warned, list) else []
    warned: set[str] = {str(name) for name in stored_warned if isinstance(name, str)}
    crossed_threshold: list[str] = []
    for path in sorted(set(files)):
        try:
            name = path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            continue
        counts[name] = counts.get(name, 0) + 1
        if counts[name] >= EDIT_WARNING_THRESHOLD and name not in warned:
            warned.add(name)
            crossed_threshold.append(name)

    try:
        directory.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps(
                {"version": 1, "counts": counts, "warned": sorted(warned)},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    except OSError as error:
        print(f"編集ループ状態を記録できませんでした: {error}", file=sys.stderr)
        return []
    return crossed_threshold


def clear_edit_state(directory: Path, turn: str) -> None:
    """ターンの編集状態ファイルを削除する。"""
    try:
        edit_state_path(directory, turn).unlink(missing_ok=True)
    except OSError as error:
        print(f"編集ループ状態を削除できませんでした: {error}", file=sys.stderr)


def edit_warning_context(paths: list[str]) -> str:
    """編集警告文を生成する。"""
    return "\n".join(
        f"同一ファイルの反復編集警告: `{path}` の編集回数が今ターンの警告閾値（{EDIT_WARNING_THRESHOLD}回）に達しました。"
        "受入条件と現在の方針を照合し、計画を見直してから編集を再開してください。"
        "これは助言通知であり作業をブロックしません。"
        for path in paths
    )


def stop_decision(
    event: dict[str, object],
    signature: str,
    previous: dict[str, object] | None,
    result: int | None,
) -> dict[str, object]:
    """Stopイベントの最終判定結果を生成する。"""
    if (
        previous
        and previous.get("signature") == signature
        and previous.get("status") in {"stagnated", "attempt_limit"}
    ):
        return {
            "systemMessage": f"品質修復を停止しました: {previous['status']}。未解決の失敗が残っています。ログを報告し、診断の見直しを求めてください。成功を主張したり検査を弱めないでください。"
        }
    if previous and previous.get("signature") == signature:
        if previous.get("result") == 0:
            return {}
        if event.get("stop_hook_active"):
            return {
                "systemMessage": "品質検査が依然として失敗しています。失敗内容とログを報告してください。成功を主張しないでください。"
            }
    if result is None or result == 0:
        return {}
    return {
        "decision": "block",
        "reason": "品質検査に失敗しました。.agents/work/.hooks のログを確認し、スコープ内の失敗を修正して再実行してください。環境上のブロッカーは明示的に報告してください。",
    }


def main(event: dict[str, object]) -> dict[str, object]:
    """ライフサイクルイベントに応じた品質検査を実行する。"""
    if event.get("hook_event_name") == "PostToolUse":
        files = edited_paths(event)
        if not files:
            return {}
        edit_warnings = edit_loop_warnings(ROOT, event, files)
        formatting = format_python(event)
        scopes: set[str] = set()
        for path in files:
            try:
                name = path.relative_to(ROOT).as_posix()
            except ValueError:
                continue
            if path.suffix == ".py":
                scopes.add("backend")
            if name.startswith("frontend/"):
                scopes.add("frontend")
            if name.startswith("scripts/"):
                scopes.add("scripts")
        failures: list[str] = (
            ["変更されたPythonファイルのフォーマットに失敗しました。"]
            if formatting
            else []
        )
        for scope in sorted(scopes):
            quick_process = subprocess.run(
                [
                    "node",
                    str(ROOT / "scripts/checks/quality.mts"),
                    "--scope",
                    scope,
                    "--phase",
                    "quick",
                    "--require-spec",
                ],
                cwd=ROOT,
                capture_output=True,
                timeout=180,
                check=False,
            )
            if quick_process.returncode:
                failures.append(
                    (quick_process.stdout + quick_process.stderr).decode(
                        "utf-8", errors="replace"
                    )
                )
        contexts: list[str] = []
        if edit_warnings:
            contexts.append(edit_warning_context(edit_warnings))
        if failures:
            contexts.append(
                "クイック品質検査に失敗しました:\n" + "\n".join(failures)[-12000:]
            )
        if contexts:
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": "\n\n".join(contexts),
                }
            }
        return {}
    if event.get("hook_event_name") != "Stop":
        return {}

    def signature_for_current_inputs() -> str:
        return hashlib.sha256(
            (
                validation_context(ROOT)
                + fingerprint(ROOT, changed_paths(ROOT))
                + fingerprint(ROOT, ["tmp/quality/task.json"])
            ).encode("utf-8")
        ).hexdigest()

    signature = signature_for_current_inputs()
    spec_signature = fingerprint(ROOT, ["tmp/quality/task.json"])
    turn = str(event.get("turn_id") or event.get("session_id") or "current")
    key = hashlib.sha256(turn.encode("utf-8")).hexdigest()[:24]
    directory = ROOT / ".agents/work/.hooks"
    directory.mkdir(parents=True, exist_ok=True)

    def finish_stop(decision: dict[str, object]) -> dict[str, object]:
        if decision.get("decision") != "block":
            clear_edit_state(directory, turn)
        return decision

    receipt = directory / f"{key}.json"
    previous: dict[str, object] | None = None
    try:
        raw_receipt = (
            json.loads(receipt.read_text(encoding="utf-8"))
            if receipt.exists()
            else None
        )
        if isinstance(raw_receipt, dict):
            previous = raw_receipt
    except ValueError, OSError:
        print("無効な品質レシートのため検査を再実行します。", file=sys.stderr)
        previous = None

    if (
        previous
        and previous.get("signature") == signature
        and (
            previous.get("result") == 0
            or event.get("stop_hook_active")
            or previous.get("status") in {"stagnated", "attempt_limit"}
        )
    ):
        return finish_stop(stop_decision(event, signature, previous, None))
    log = directory / f"{key}.log"
    report = directory / f"{key}.report.json"
    report.unlink(missing_ok=True)
    exit_code = 1
    status = "failed"
    with log.open("w", encoding="utf-8") as output:
        try:
            exit_code = subprocess.run(
                [
                    "node",
                    str(ROOT / "scripts/checks/quality.mts"),
                    "--changed",
                    "--report",
                    str(report),
                    "--require-spec",
                ],
                cwd=ROOT,
                stdout=output,
                stderr=subprocess.STDOUT,
                timeout=540,
                check=False,
            ).returncode
            status = "passed" if exit_code == 0 else "failed"
        except (OSError, subprocess.TimeoutExpired) as error:
            output.write(f"品質ランナーの実行に失敗しました: {error}\n")
            exit_code = 1
            status = (
                "timeout"
                if isinstance(error, subprocess.TimeoutExpired)
                else "start_error"
            )
    # 検査実行中にファイルが変更された場合は成功とみなさない
    if signature_for_current_inputs() != signature:
        exit_code = 1
        status = "inputs_changed"
        with log.open("a", encoding="utf-8") as output:
            output.write(
                "実行中にファイルが変更されました。現在の内容で再実行してください。\n"
            )
    structured: dict[str, object] | None = None
    try:
        raw_struct = (
            json.loads(report.read_text(encoding="utf-8")) if report.exists() else None
        )
        if isinstance(raw_struct, dict):
            structured = raw_struct
    except ValueError, OSError:
        structured = None
    failure_key, feedback = report_feedback(structured)
    state = repair_state(
        previous
        if previous and previous.get("spec_signature") == spec_signature
        else None,
        exit_code,
        failure_key if status == "failed" else None,
    )
    if state.get("terminal"):
        status = str(state["terminal"])
    current: dict[str, object] = {
        "signature": signature,
        "spec_signature": spec_signature,
        "result": exit_code,
        "status": status,
        "log": log.name,
        "report": report.name if report.exists() else None,
        **state,
    }
    receipt.write_text(
        json.dumps(current, ensure_ascii=False),
        encoding="utf-8",
    )
    if state.get("terminal"):
        return finish_stop(stop_decision(event, signature, current, exit_code))
    decision = stop_decision(event, signature, previous, exit_code)
    if decision.get("decision") == "block":
        reason_str = str(decision.get("reason", ""))
        decision["reason"] = (
            reason_str + f"\nLog: {log.relative_to(ROOT).as_posix()}\n{feedback}"
        )
    return finish_stop(decision)


if __name__ == "__main__":
    try:
        raw_event = json.load(sys.stdin)
        parsed: dict[str, object] = raw_event if isinstance(raw_event, dict) else {}
        print(json.dumps(main(parsed), ensure_ascii=False))
    except Exception as error:
        print(f"品質Hook実行エラー: {error}", file=sys.stderr)
        raise SystemExit(1) from error
