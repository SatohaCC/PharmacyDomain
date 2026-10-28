"""Applicationのget_corporateを定義する。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Self

from app.domain.corporate.entities import Corporate


@dataclass(frozen=True, kw_only=True)
class CorporateResponseDto:
    """取得結果として画面やAPIに返すデータ構造（DTO）"""

    id: str
    name: str
    representative_name: str
    is_active: bool

    @classmethod
    def from_entity(cls, corporate: Corporate) -> Self:
        """Corporate エンティティから DTO を復元するファクトリメソッド"""
        return cls(
            id=str(corporate.id.value),
            name=corporate.name.value,
            representative_name=corporate.representative_name.full_name,
            is_active=corporate.is_active,
        )
