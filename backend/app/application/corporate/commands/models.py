"""Applicationのmodelsを定義する。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class RegisterCorporateCommand:
    """法人登録に必要なパラメータをまとめた Command (DTO)"""

    name: str
    representative_last_name: str
    representative_first_name: str
    corporate_type: str = "stock_company"
    corporate_number: str | None = None
    invoice_number: str | None = None
    postal_code: str | None = None
    address_line: str | None = None
    phone_number: str | None = None
    email: str | None = None
