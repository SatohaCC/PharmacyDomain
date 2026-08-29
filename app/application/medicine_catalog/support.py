"""MedicineCatalogユースケース間で共有する入力変換処理。

``to_optional_text`` は Shared Kernel の定義を**再エクスポートするだけ**にする。
"""

from __future__ import annotations

from enum import StrEnum

from app.base.application.support import to_optional_text
from app.base.domain.exceptions import DomainValidationError

__all__ = ["parse_enum", "required_text", "to_optional_text"]


def required_text(raw: str | None, field_name: str) -> str:
    """必須文字列を正規化し、未入力ならドメイン例外を送出する。"""
    value = to_optional_text(raw)
    if value is None:
        raise DomainValidationError(f"{field_name}は必須です。")
    return value


def parse_enum[E: StrEnum](enum_type: type[E], raw: str, field_name: str) -> E:
    """入力文字列を指定の列挙へ変換する。"""
    try:
        return enum_type(raw)
    except ValueError as exc:
        raise DomainValidationError(f"{field_name}が不正です。") from exc
