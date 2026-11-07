"""受付ドメインのクエリ入力モデル。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class GetCurrentRecordValuesQuery:
    """受付の今回記載欄入力値の取得条件。"""

    corporate_id: str
    store_id: str
    reception_id: str


__all__ = ["GetCurrentRecordValuesQuery"]
