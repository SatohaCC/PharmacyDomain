"""Applicationのmodelsを定義する。"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.corporate.identifiers import CorporateId


@dataclass(frozen=True, kw_only=True)
class RegisteredCorporate:
    """登録完了した法人のIDとログインコード。"""

    id: CorporateId
    login_code: str


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
