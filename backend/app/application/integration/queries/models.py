"""ApplicationのIntegrationクエリモデルを定義する。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class GetNsipsSourceQuery:
    """NSIPS原本データ取得クエリ。"""

    corporate_id: str
    store_id: str
    reception_id: str
