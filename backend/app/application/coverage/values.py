"""Applicationのvaluesを定義する。"""

from __future__ import annotations

from app.application.common.input_normalization import to_optional_text
from app.domain.foundation.exceptions import DomainValidationError


def required_text(raw: str | None, field_name: str) -> str:
    """必須文字列を正規化し、未入力ならドメイン例外を送出する。"""
    value = to_optional_text(raw)
    if value is None:
        raise DomainValidationError(f"{field_name}は必須です。")
    return value
