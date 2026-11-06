"""診断IDに基づいて修復試行回数を制限し、同一失敗の繰り返しによるループを防止する。"""

from __future__ import annotations

import hashlib
import json


def report_feedback(report: dict[str, object] | None) -> tuple[str | None, str]:
    """品質レポートを解析し、安定した失敗識別キーと診断メッセージを返す。"""
    if not report or not isinstance(report.get("tasks"), list):
        return (
            None,
            "品質ログおよび docs/development.md を確認してください。構造化診断情報は利用できません。",
        )
    raw_tasks = report.get("tasks")
    task_list = raw_tasks if isinstance(raw_tasks, list) else []
    failures = [
        task
        for task in task_list
        if isinstance(task, dict) and task.get("status") != "passed"
    ]
    identities: list[str] = []
    messages: list[str] = []
    complete = bool(failures)
    for task in failures:
        raw_feedback = task.get("feedback")
        feedback = raw_feedback if isinstance(raw_feedback, dict) else {}
        identity = feedback.get("identity")
        if isinstance(identity, str) and identity:
            identities.append(identity)
        else:
            complete = False
        label = str(task.get("label", "検査"))
        status = str(task.get("status", "不明"))
        diagnostics = feedback.get("diagnostics", [])
        suggestion = str(
            feedback.get("suggestion", "ログと受入条件を確認してください。")
        )
        docs = str(feedback.get("docs", "docs/development.md"))
        messages.append(
            f"{label}: {status}\n"
            f"診断情報: {diagnostics}\n"
            f"次の行動: {suggestion}\n"
            f"参照文書: {docs}"
        )
    key = (
        hashlib.sha256(json.dumps(sorted(identities)).encode("utf-8")).hexdigest()
        if complete
        else None
    )
    return key, "\n".join(messages)[:10000]


def repair_state(
    previous: dict[str, object] | None, result: int, failure_key: str | None
) -> dict[str, object]:
    """修復試行の繰り返し状態を更新し、停滞または上限到達を判定する。"""
    if result == 0:
        return {"attempts": 0, "repeated_failures": 0, "failure_key": None}
    prev = previous or {}
    raw_attempts = prev.get("attempts", 0)
    attempts = int(str(raw_attempts)) + 1 if isinstance(raw_attempts, (int, str)) else 1
    raw_repeated = prev.get("repeated_failures", 0)
    repeated = (
        int(str(raw_repeated)) + 1
        if failure_key
        and prev.get("failure_key") == failure_key
        and isinstance(raw_repeated, (int, str))
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
