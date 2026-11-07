"""NSIPSファイル名から操作種別とファイルIDを判定する。"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.application.integration.boundary_models import NsipsOperation
from app.application.integration.errors import UnknownNsipsFileNameError

NSIPS_FILE_NAME_PATTERN = re.compile(
    r"^(?P<operation>[A-Za-z])[_-](?P<file_id>[0-9A-Za-z][0-9A-Za-z._-]*)"
    r"\.(?:xml|csv|dat|txt|json)$",
    re.IGNORECASE,
)
"""<操作1文字>[_-]<ファイルID>.<拡張子> を想定したパターン（例 A_20260726-001.xml）。"""

_OPERATION_BY_LETTER: dict[str, NsipsOperation] = {
    "A": NsipsOperation.CREATE,
    "U": NsipsOperation.UPDATE,
    "B": NsipsOperation.CREATE,
    "D": NsipsOperation.DELETE,
}


@dataclass(frozen=True, kw_only=True)
class ParsedNsipsFileName:
    """ファイル名から取り出した、取込の分岐に必要な値。"""

    file_id: str
    operation: NsipsOperation
    is_bulk: bool = False


def parse_nsips_file_name(file_name: str) -> ParsedNsipsFileName:
    """NSIPSファイル名（ディレクトリを含まない）を操作種別とファイルIDに分解する。

    Raises:
        UnknownNsipsFileNameError: パターン不一致、または操作文字が未知の場合。
    """
    match = NSIPS_FILE_NAME_PATTERN.match(file_name.strip())
    if match is None:
        raise UnknownNsipsFileNameError(
            f"NSIPSファイル名 '{file_name}' が想定パターンに一致しません。"
        )

    letter = match.group("operation").upper()
    operation = _OPERATION_BY_LETTER.get(letter)
    if operation is None:
        raise UnknownNsipsFileNameError(
            f"NSIPSファイル名 '{file_name}' の操作文字 '{letter}' を判定できません。"
        )

    return ParsedNsipsFileName(
        file_id=match.group("file_id"),
        operation=operation,
        is_bulk=letter == "B",
    )


__all__ = [
    "NSIPS_FILE_NAME_PATTERN",
    "ParsedNsipsFileName",
    "UnknownNsipsFileNameError",
    "parse_nsips_file_name",
]
