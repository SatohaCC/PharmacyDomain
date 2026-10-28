"""Applicationのimport_yj_catalogを定義する。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, kw_only=True)
class ImportYjCatalogResultDto:
    """インポート実行結果DTO。"""

    total_rows: int
    imported_count: int
    skipped_count: int
    catalog_version: date
