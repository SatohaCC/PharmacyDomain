"""公開変更ファイル内の個人情報・機密情報の混入を検知する（機密内容自体は出力しない）。"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from tools.hooks.quality_gate import changed_paths  # noqa: E402

HOME = re.compile(r"(?i)C:[\\/]+Users[\\/]+([^\\/\s\"'<>`]+)")
DEFAULT_ALLOWED = {"username", "user", "public", "default"}
SECRET_PATTERNS = [
    re.compile(
        r"\b(?:ghp_[a-zA-Z0-9]{36}|github_pat_[a-zA-Z0-9]{22}_[a-zA-Z0-9]{59}|sk-[a-zA-Z0-9]{24,}|AKIA[0-9A-Z]{16})\b"
    ),
    re.compile(
        r"""(?i)['"]?(?:my_?number|マイナンバー|個人番号)['"]?\s*[:=]\s*['"]?\d{12}['"]?"""
    ),
]


def scan(root: Path, paths: list[str], config: dict[str, object]) -> list[str]:
    """対象ファイルを走査し、個人パスや機密情報を含むファイルと行番号を返す。"""
    raw_allowed = config.get("allowed_user_segments", DEFAULT_ALLOWED)
    allowed_list = (
        raw_allowed if isinstance(raw_allowed, (set, list, tuple)) else DEFAULT_ALLOWED
    )
    allowed = {str(v).casefold() for v in allowed_list}
    raw_tokens = config.get("blocked_literals", [])
    tokens = [str(t) for t in raw_tokens] if isinstance(raw_tokens, list) else []
    results: list[str] = []
    for name in paths:
        path = root / name
        if not path.is_file() or path.is_symlink():
            continue
        raw = path.read_bytes()
        text: str
        if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
            text = raw.decode("utf-16")
        elif b"\0" in raw:
            continue
        else:
            text = raw.decode("utf-8-sig", errors="replace")
        for number, line in enumerate(text.splitlines(), 1):
            personal = any(
                match.group(1).rstrip(".,;:)").casefold() not in allowed
                and not match.group(1).startswith(("$", "%", "{"))
                for match in HOME.finditer(line)
            )
            has_secret = any(pat.search(line) for pat in SECRET_PATTERNS)
            if (
                personal
                or has_secret
                or any(
                    token and token.casefold() in line.casefold() for token in tokens
                )
            ):
                results.append(f"{name}:{number}")
    return results


def main(event: dict[str, object]) -> dict[str, object]:
    """Hookイベントを受け取り、プライバシー検査判定を返す。"""
    if event.get("hook_event_name") not in {"PostToolUse", "Stop"}:
        return {}
    policy = Path.home() / ".config/git/hooks/privacy-config.json"
    config: dict[str, object] = (
        json.loads(policy.read_text(encoding="utf-8")) if policy.exists() else {}
    )
    results = scan(ROOT, changed_paths(ROOT), config)
    if not results:
        return {}
    reason = (
        "プライバシー検査に失敗しました（個人ホームディレクトリパスまたは機密文字列を検出）。該当箇所:\n"
        + "\n".join(results[:50])
    )
    if event.get("hook_event_name") == "PostToolUse":
        return {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": reason,
            }
        }
    if event.get("stop_hook_active"):
        return {
            "systemMessage": reason
            + "\n未解決の指摘事項を報告してください。成功を主張しないでください。"
        }
    return {"decision": "block", "reason": reason}


if __name__ == "__main__":
    try:
        raw_event = json.load(sys.stdin)
        parsed_event: dict[str, object] = (
            raw_event if isinstance(raw_event, dict) else {}
        )
        print(json.dumps(main(parsed_event), ensure_ascii=False))
    except (OSError, ValueError, TypeError, AttributeError) as error:
        print(
            f"プライバシー検査を完了できませんでした: {type(error).__name__}",
            file=sys.stderr,
        )
        raise SystemExit(2) from None
