"""Applicationのmodelsを定義する。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, kw_only=True)
class StoreOpeningStatusQuery:
    """開局状況の照会。at を省くと注入した時計の現在時刻で判定する。"""

    corporate_id: str
    store_id: str
    at: datetime | None = None


@dataclass(frozen=True, kw_only=True)
class GetStoreQuery:
    """店舗詳細取得の入力データ（DTO）"""

    corporate_id: str
    store_id: str


@dataclass(frozen=True, kw_only=True)
class ListStoresQuery:
    """店舗一覧取得の入力データ（DTO）。"""

    corporate_id: str


@dataclass(frozen=True, kw_only=True)
class GetEffectivePolicyQuery:
    """店舗の実効ポリシー照会条件。"""

    corporate_id: str
    store_id: str
