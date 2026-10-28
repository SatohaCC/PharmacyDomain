"""Applicationのmodelsを定義する。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class GetDispensingQuery:
    """調剤セッション取得の入力データ。"""

    corporate_id: str
    dispensing_id: str


@dataclass(frozen=True, kw_only=True)
class ListDispensingsByPrescriptionQuery:
    """調剤セッション一覧取得の入力データ。"""

    corporate_id: str
    prescription_id: str
