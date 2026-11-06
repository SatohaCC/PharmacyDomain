"""Adapt Codex and Antigravity events to the shared quality runner; keep checks outside the hook."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.hooks.format_edited_python import edited_paths
from scripts.hooks.format_edited_python import main as format_python
from scripts.hooks.quality_feedback import repair_state, report_feedback

EDIT_WARNING_THRESHOLD = 5


def changed_paths(root: Path) -> list[str]:
    paths = set()
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
    """Bind receipts to HEAD and the tracked validation configuration."""
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
            or name.startswith(("scripts/checks/", "scripts/hooks/"))
            or Path(name).name.startswith(
                (".python-version", ".nvmrc", ".importlinter")
            )
        )
    ]
    return head.decode("utf-8").strip() + ":" + fingerprint(root, inputs)


def fingerprint(root: Path, paths: list[str]) -> str:
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
    key = hashlib.sha256(turn.encode("utf-8")).hexdigest()[:24]
    return directory / f"{key}.edits.json"


def edit_loop_warnings(root: Path, event: dict, files: list[Path]) -> list[str]:
    if not files:
        return []

    turn = str(event.get("turn_id") or event.get("session_id") or "current")
    directory = root / ".agents/work/.hooks"
    state_path = edit_state_path(directory, turn)
    try:
        stored = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        stored = {}
    if (
        not isinstance(stored, dict)
        or stored.get("version") != 1
        or not isinstance(stored.get("counts"), dict)
    ):
        stored = {}

    counts = {
        name: count
        for name, count in stored.get("counts", {}).items()
        if isinstance(name, str) and type(count) is int and count > 0
    }
    stored_warned = stored.get("warned", [])
    if not isinstance(stored_warned, list):
        stored_warned = []
    warned = {name for name in stored_warned if isinstance(name, str)}
    crossed_threshold = []
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
        print(f"Could not record edit-loop state: {error}", file=sys.stderr)
        return []
    return crossed_threshold


def clear_edit_state(directory: Path, turn: str) -> None:
    try:
        edit_state_path(directory, turn).unlink(missing_ok=True)
    except OSError as error:
        print(f"Could not clear edit-loop state: {error}", file=sys.stderr)


def edit_warning_context(paths: list[str]) -> str:
    return "\n".join(
        f"Repeated editing reminder: `{path}` has reached {EDIT_WARNING_THRESHOLD} edits this turn. "
        "Pause to compare the approach with the acceptance criteria and reconsider the plan before editing again. "
        "This is advisory and does not block the work."
        for path in paths
    )


def stop_decision(
    event: dict, signature: str, previous: dict | None, result: int | None
) -> dict:
    if (
        previous
        and previous.get("signature") == signature
        and previous.get("status") in {"stagnated", "attempt_limit"}
    ):
        return {
            "systemMessage": f"Quality repair stopped: {previous['status']}. Unresolved failures remain. Report the log and request a revised diagnosis; do not claim success or weaken checks."
        }
    if previous and previous.get("signature") == signature:
        if previous.get("result") == 0:
            return {}
        if event.get("stop_hook_active"):
            return {
                "systemMessage": "Quality checks still fail. Report failures and the log; do not claim success."
            }
    if result is None or result == 0:
        return {}
    return {
        "decision": "block",
        "reason": "Quality checks failed. Inspect .agents/work/.hooks logs, fix scoped failures, and rerun. Report environment blockers explicitly.",
    }


def main(event: dict) -> dict:
    if event.get("hook_event_name") == "PostToolUse":
        files = edited_paths(event)
        if not files:
            return {}
        edit_warnings = edit_loop_warnings(ROOT, event, files)
        formatting = format_python(event)
        scopes = set()
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
        failures = ["Formatting edited Python files failed."] if formatting else []
        for scope in sorted(scopes):
            quick_process = subprocess.run(
                [
                    "node",
                    str(ROOT / "scripts/checks/quality.mjs"),
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
        contexts = []
        if edit_warnings:
            contexts.append(edit_warning_context(edit_warnings))
        if failures:
            contexts.append("Quick checks failed:\n" + "\n".join(failures)[-12000:])
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

    def finish_stop(decision: dict) -> dict:
        if decision.get("decision") != "block":
            clear_edit_state(directory, turn)
        return decision

    receipt = directory / f"{key}.json"
    try:
        previous = (
            json.loads(receipt.read_text(encoding="utf-8"))
            if receipt.exists()
            else None
        )
        if not isinstance(previous, dict):
            previous = None
    except (ValueError, OSError):
        print("Invalid quality receipt; running checks again.", file=sys.stderr)
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
    with log.open("w", encoding="utf-8") as output:
        try:
            exit_code = subprocess.run(
                [
                    "node",
                    str(ROOT / "scripts/checks/quality.mjs"),
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
            output.write(f"Quality runner failed: {error}\n")
            exit_code = 1
            status = (
                "timeout"
                if isinstance(error, subprocess.TimeoutExpired)
                else "start_error"
            )
    # A check must not certify files changed during execution (including generated output).
    if signature_for_current_inputs() != signature:
        exit_code = 1
        status = "inputs_changed"
        with log.open("a", encoding="utf-8") as output:
            output.write(
                "Files changed during validation; rerun against the current contents.\n"
            )
    try:
        structured = (
            json.loads(report.read_text(encoding="utf-8")) if report.exists() else None
        )
        if not isinstance(structured, dict):
            structured = None
    except (ValueError, OSError):
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
        status = state["terminal"]
    current = {
        "signature": signature,
        "spec_signature": spec_signature,
        "result": exit_code,
        "status": status,
        "log": log.name,
        "report": report.name if report.exists() else None,
        **state,
    }
    receipt.write_text(
        json.dumps(current),
        encoding="utf-8",
    )
    if state.get("terminal"):
        return finish_stop(stop_decision(event, signature, current, exit_code))
    decision = stop_decision(event, signature, previous, exit_code)
    if decision.get("decision") == "block":
        decision["reason"] += f"\nLog: {log.relative_to(ROOT).as_posix()}\n{feedback}"
    return finish_stop(decision)


if __name__ == "__main__":
    try:
        print(json.dumps(main(json.load(sys.stdin)), ensure_ascii=False))
    except Exception as error:
        print(f"Quality hook failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
