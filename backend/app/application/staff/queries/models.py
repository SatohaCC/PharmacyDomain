"""Applicationのmodelsを定義する。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, kw_only=True)
class GetStaffQuery:
    """スタッフ詳細取得の入力データ（DTO）。"""

    corporate_id: str
    staff_id: str
    target_date: date | None = None


@dataclass(frozen=True, kw_only=True)
class ListStaffsQuery:
    """スタッフ一覧取得の入力データ（DTO）。"""

    corporate_id: str
