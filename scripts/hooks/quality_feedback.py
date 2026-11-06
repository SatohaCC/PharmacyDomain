"""Bound repair attempts using diagnostic identities, never source hashes alone."""

from __future__ import annotations

import hashlib
import json


def report_feedback(report: dict | None) -> tuple[str | None, str]:
    if not report or not isinstance(report.get("tasks"), list):
        return (
            None,
            "Read the quality log and docs/development.md; no structured diagnostics are available.",
        )
    failures = [
        task
        for task in report["tasks"]
        if isinstance(task, dict) and task.get("status") != "passed"
    ]
    identities = []
    messages = []
    complete = bool(failures)
    for task in failures:
        feedback = task.get("feedback") or {}
        if not isinstance(feedback, dict):
            feedback = {}
        identity = feedback.get("identity")
        if isinstance(identity, str) and identity:
            identities.append(identity)
        else:
            complete = False
        messages.append(
            f"{task.get('label', 'Check')}: {task.get('status', 'unknown')}\n"
            f"Diagnostics: {feedback.get('diagnostics', [])}\n"
            f"Next: {feedback.get('suggestion', 'Inspect the log and acceptance criterion.')}\n"
            f"Reference: {feedback.get('docs', 'docs/development.md')}"
        )
    key = (
        hashlib.sha256(json.dumps(sorted(identities)).encode("utf-8")).hexdigest()
        if complete
        else None
    )
    return key, "\n".join(messages)[:10000]


def repair_state(previous: dict | None, result: int, failure_key: str | None) -> dict:
    if result == 0:
        return {"attempts": 0, "repeated_failures": 0, "failure_key": None}
    previous = previous or {}
    attempts = int(previous.get("attempts", 0)) + 1
    repeated = (
        int(previous.get("repeated_failures", 0)) + 1
        if failure_key and previous.get("failure_key") == failure_key
        else 1
    )
    return {
        "attempts": attempts,
        "repeated_failures": repeated if failure_key else 0,
        "failure_key": failure_key,
        "terminal": "stagnated"
        if failure_key and repeated >= 3
        else "attempt_limit"
        if attempts >= 6
        else None,
    }
