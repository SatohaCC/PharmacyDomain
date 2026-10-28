"""Applicationのmodelsを定義する。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, kw_only=True)
class GetLastCoverageSelectionQuery:
    """最新選択候補取得の入力データ。"""

    corporate_id: str
    store_id: str
    patient_id: str
    applied_on: date


@dataclass(frozen=True, kw_only=True)
class GetPatientCoverageQuery:
    """患者資格取得の入力データ（DTO）。"""

    corporate_id: str
    coverage_id: str


@dataclass(frozen=True, kw_only=True)
class ListPatientCoveragesQuery:
    """患者資格一覧取得の入力データ（DTO）。"""

    corporate_id: str
    patient_id: str
