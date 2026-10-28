"""Applicationのmerge_patientsを定義する。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, kw_only=True)
class MergePatientsResultDto:
    """患者名寄せ統合の完了DTO。"""

    source_patient_id: str
    target_patient_id: str
    merged_at: datetime
