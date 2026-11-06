"""Check changed public files without echoing sensitive matched contents."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.hooks.quality_gate import changed_paths

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


def scan(root: Path, paths: list[str], config: dict) -> list[str]:
    allowed = {
        v.casefold() for v in config.get("allowed_user_segments", DEFAULT_ALLOWED)
    }
    tokens = config.get("blocked_literals", [])
    results = []
    for name in paths:
        path = root / name
        if not path.is_file() or path.is_symlink():
            continue
        raw = path.read_bytes()
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


def main(event: dict) -> dict:
    if event.get("hook_event_name") not in {"PostToolUse", "Stop"}:
        return {}
    # Reuse the existing local policy without publishing its private literals.
    policy = Path.home() / ".config/git/hooks/privacy-config.json"
    config = json.loads(policy.read_text(encoding="utf-8")) if policy.exists() else {}
    results = scan(ROOT, changed_paths(ROOT), config)
    if not results:
        return {}
    reason = (
        "Privacy check failed (personal home path or blocked literal). Locations only:\n"
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
            + "\nReport unresolved findings; do not claim success."
        }
    return {"decision": "block", "reason": reason}


if __name__ == "__main__":
    try:
        print(json.dumps(main(json.load(sys.stdin)), ensure_ascii=False))
    except (OSError, ValueError, TypeError, AttributeError) as error:
        print(
            f"Privacy check could not complete: {type(error).__name__}", file=sys.stderr
        )
        raise SystemExit(2) from None
