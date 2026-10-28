"""Applicationのmodelsを定義する。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class RegisterCorporateCommand:
    """法人登録に必要なパラメータをまとめた Command (DTO)"""

    name: str
    representative_last_name: str
    representative_first_name: str
