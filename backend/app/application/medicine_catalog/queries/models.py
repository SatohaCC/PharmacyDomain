"""Applicationのmodelsを定義する。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, kw_only=True)
class GetEffectiveMedicineQuery:
    """指定日に有効なマスタ行の取得の入力データ。"""

    code_type: str
    code: str
    as_of: date
