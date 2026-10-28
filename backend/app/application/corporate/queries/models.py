"""Applicationのmodelsを定義する。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class ListCorporatesQuery:
    """法人一覧の検索条件。"""

    name: str | None = None
    status: str | None = None
    cursor: str | None = None
    limit: int = 50
