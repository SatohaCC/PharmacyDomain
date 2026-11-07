"""薬歴ブロッククエリのDTO定義。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, kw_only=True)
class MedicationHistoryBlockDto:
    """薬歴ブロックのクエリ応答DTO。"""

    id: str
    category_code: str
    category_name: str
    category_badge_label: str
    content: str
    display_order: int
    source_module: str
    source_id: str | None = None
    updated_by: str | None = None
    updated_by_name: str = ""
    updated_at: datetime | None = None
