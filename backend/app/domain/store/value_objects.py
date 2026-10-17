"""店舗の名称・所在地・連絡先を表す複合値。"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar, Self

from app.domain.foundation.exceptions import DomainValidationError
from app.domain.foundation.value_object import ValueObject
from app.domain.store.primitives import (
    StoreAddressLine,
    StoreEmailAddress,
    StoreFaxNumber,
    StoreName,
    StoreNameKana,
    StoreNameRomaji,
    StorePhoneNumber,
    StorePostalCode,
)


@dataclass(frozen=True, kw_only=True)
class StoreNames(ValueObject):
    """店舗名の一式（正式名称・フリガナ・ローマ字）"""

    name: StoreName
    kana: StoreNameKana
    romaji: StoreNameRomaji | None = None

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "name": "正式名称",
        "kana": "フリガナ",
        "romaji": "ローマ字",
    }


@dataclass(frozen=True, kw_only=True)
class StoreAddress(ValueObject):
    """所在地情報（郵便番号と住所）。"""

    postal_code: StorePostalCode
    address: StoreAddressLine  # 例: "〇〇1-2-3"

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "postal_code": "郵便番号",
        "address": "住所",
    }


@dataclass(frozen=True, kw_only=True)
class ContactInfo(ValueObject):
    """連絡先情報。"""

    phone_number: StorePhoneNumber
    fax_number: StoreFaxNumber | None = None
    email: StoreEmailAddress | None = None

    @classmethod
    def create(
        cls,
        *,
        phone_number: StorePhoneNumber,
        fax_number: StoreFaxNumber | None = None,
        email: StoreEmailAddress | None = None,
    ) -> Self:
        """空の任意連絡先を ``None`` に正規化して生成する。"""
        return cls(
            phone_number=phone_number,
            fax_number=fax_number if fax_number and fax_number.value else None,
            email=email if email and email.value else None,
        )

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "phone_number": "電話番号",
        "fax_number": "FAX番号",
        "email": "メールアドレス",
    }

    def _normalize_fields(self) -> None:
        """未発行の空FAXを未設定へ正規化する。"""
        if isinstance(self.fax_number, StoreFaxNumber) and not self.fax_number.value:
            object.__setattr__(self, "fax_number", None)

    def validate(self) -> None:
        """必須の電話番号が空でないことを検証する。"""
        if not self.phone_number.value:
            raise DomainValidationError("電話番号は空にできません。")
