"""Applicationのmodelsを定義する。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class GetPrescriptionQuery:
    """処方箋取得の入力データ。"""

    corporate_id: str
    prescription_id: str
