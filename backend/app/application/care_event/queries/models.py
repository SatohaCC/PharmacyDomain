"""Applicationのmodelsを定義する。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class GetEventQuery:
    """Event取得の入力。"""

    corporate_id: str
    event_id: str


@dataclass(frozen=True, kw_only=True)
class ListRelatedEventCandidatesQuery:
    """関連候補一覧の入力。"""

    corporate_id: str
    store_id: str
    patient_id: str
