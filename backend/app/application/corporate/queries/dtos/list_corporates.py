"""Applicationのlist_corporatesを定義する。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.corporate.queries.dtos.get_corporate import CorporateResponseDto


@dataclass(frozen=True, kw_only=True)
class CorporatePageDto:
    """法人一覧の一ページ。"""

    items: tuple[CorporateResponseDto, ...]
    next_cursor: str | None
