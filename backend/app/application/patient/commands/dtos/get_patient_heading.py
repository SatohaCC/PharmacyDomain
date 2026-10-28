"""Applicationのget_patient_headingを定義する。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class PatientHeadingRevisionDto:
    """患者頭書き1改訂分の応答。"""

    revision: int
    summary: str | None
    notes: str | None
    person_id: str
    account_id: str
    recorded_at: str


@dataclass(frozen=True, kw_only=True)
class PatientHeadingDto:
    """患者頭書きの現在値と変更履歴の応答。"""

    patient_id: str
    revision: int
    summary: str | None
    notes: str | None
    updated_by_person_id: str | None
    updated_by_account_id: str | None
    updated_at: str | None
    history: tuple[PatientHeadingRevisionDto, ...]
