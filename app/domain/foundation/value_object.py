"""ドメイン層で使う複合 Value Object の基底クラス。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar

from app.domain.foundation.field_guard import ensure_declared_field_types


@dataclass(frozen=True, kw_only=True)
class ValueObject:
    """複合 Value Object の初期化順序を統一する基底クラス。"""

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {}

    def __post_init__(self) -> None:
        """正規化、宣言型の照合、業務ルール検証を順に実行する。"""
        self._normalize_fields()
        ensure_declared_field_types(self, labels=self._FIELD_LABELS)
        self.validate()

    def _normalize_fields(self) -> None:
        """派生クラスが複合フィールドを正規化するためのフック。"""
        return None

    def validate(self) -> None:
        """派生クラスが値オブジェクト固有の不変条件を検証するためのフック。"""
        return None
