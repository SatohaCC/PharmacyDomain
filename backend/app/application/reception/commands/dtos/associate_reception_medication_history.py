"""Applicationのassociate_reception_medication_historyを定義する。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class AssociateReceptionMedicationHistoryResultDto:
    """受付と薬歴の関連結果。"""

    reception_id: str
    medication_history_id: str
