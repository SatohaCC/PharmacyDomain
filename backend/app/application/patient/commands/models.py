"""Applicationのmodelsを定義する。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

_PROFILE_FIELDS = ("gender", "postal_code", "address", "phone_number")


@dataclass(frozen=True, kw_only=True)
class RegisterPatientCommand:
    """患者登録に必要な入力データ（DTO）。"""

    corporate_id: str
    last_name: str
    first_name: str
    last_name_kana: str
    first_name_kana: str
    birth_date: date | None = None
    gender: str | None = None
    postal_code: str | None = None
    address: str | None = None
    phone_number: str | None = None


@dataclass(frozen=True, kw_only=True)
class RegisterPatientExternalIdentifierCommand:
    """外部患者ID登録の入力データ（DTO）。"""

    corporate_id: str
    patient_id: str
    system_name: str
    external_patient_id: str
    store_id: str | None = None
