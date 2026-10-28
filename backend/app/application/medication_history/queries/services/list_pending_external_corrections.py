"""Applicationのlist_pending_external_correctionsを定義する。"""

from __future__ import annotations

import base64
import json


def _encode_cursor(record_id: str, correction_id: str) -> str:
    """複合キーを不透明なURL-safe cursorへ変換する。"""
    value = json.dumps([record_id, correction_id], separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[str, str]:
    """cursorを検証し、複合キーへ戻す。"""
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(padded).decode())
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("一覧cursorが不正です。") from exc
    if (
        not isinstance(decoded, list)
        or len(decoded) != 2
        or (not all(isinstance(item, str) for item in decoded))
    ):
        raise ValueError("一覧cursorが不正です。")
    return (decoded[0], decoded[1])
