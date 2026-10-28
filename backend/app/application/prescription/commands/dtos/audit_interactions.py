"""Applicationのaudit_interactionsを定義する。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class DrugInteractionPairDto:
    """飲み合わせ判定結果DTO。"""

    medicine_a: str
    medicine_b: str
    severity: str
    severity_label: str
    clinical_condition: str
    mechanism: str
    recommendation: str


@dataclass(frozen=True, kw_only=True)
class DrugInteractionAuditReportDto:
    """相互作用鑑査レポートDTO。"""

    target_yj_codes: list[str]
    total_combinations: int
    contraindicated_count: int
    precaution_count: int
    has_contraindications: bool
    has_precautions: bool
    pairs: list[DrugInteractionPairDto]
