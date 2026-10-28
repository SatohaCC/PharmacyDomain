"""Applicationのlist_related_candidatesを定義する。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class RelatedEventCandidateDto:
    """関連Eventとして選べる最小限の情報。"""

    event_id: str
    store_id: str
    event_type_name: str
    occurred_at: str | None
    occurred_at_is_unknown: bool
    created_at: str
