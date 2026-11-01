"""corporateの単一値と列挙・検証規則。"""

from __future__ import annotations

import re
from enum import StrEnum

from app.domain.foundation.exceptions import DomainValidationError
from app.domain.foundation.primitives.primitives import (
    BaseAddress,
    BaseEmailAddress,
    BaseNormalizedString,
    BasePositiveInt,
    BasePostalCode,
    BaseTelephoneNumber,
)


class CorporateStatus(StrEnum):
    """法人の利用状態。"""

    ACTIVE = "active"
    INACTIVE = "inactive"


class CorporateType(StrEnum):
    """法人格種別。"""

    STOCK_COMPANY = "stock_company"  # 株式会社
    LIMITED_LIABILITY_COMPANY = "limited_liability_company"  # 合同会社
    MEDICAL_CORPORATION = "medical_corporation"  # 医療法人
    GENERAL_INCORPORATED_ASSOCIATION = (
        "general_incorporated_association"  # 一般社団法人
    )
    OTHER = "other"  # その他

    @property
    def label(self) -> str:
        labels = {
            self.STOCK_COMPANY: "株式会社",
            self.LIMITED_LIABILITY_COMPANY: "合同会社",
            self.MEDICAL_CORPORATION: "医療法人",
            self.GENERAL_INCORPORATED_ASSOCIATION: "一般社団法人",
            self.OTHER: "その他",
        }
        return labels[self]


class CorporateNumber(BaseNormalizedString):
    """国税庁法人番号（13桁数字、最上位桁は公定チェックディジット）。"""

    def _normalize(self, value: str) -> str:
        if isinstance(value, str):
            # 全角数字を半角数字へ変換、空白とハイフンを除去
            normalized = value.translate(
                str.maketrans("０１２３４５６７８９", "0123456789")
            )
            return re.sub(r"[\-\sー−]", "", normalized)
        return value

    def validate(self) -> None:
        if not self.value:
            raise DomainValidationError("法人番号は空にできません。")
        if not re.fullmatch(r"[0-9]{13}", self.value):
            raise DomainValidationError("法人番号は半角数字13桁で入力してください。")

        # チェックディジット（国税庁公定アルゴリズム）の検証
        check_digit = int(self.value[0])
        base_digits = self.value[1:]  # 12桁

        # 基礎番号の各桁（右端からn=1..12）に対し、奇数桁に1、偶数桁に2を乗じた和
        # base_digits の index 11 が n=1 (奇数), index 0 が n=12 (偶数)
        total_sum = sum(
            int(digit) * (1 if (12 - idx) % 2 == 1 else 2)
            for idx, digit in enumerate(base_digits)
        )
        rem = total_sum % 9
        expected_check_digit = 9 if rem == 0 else 9 - rem

        if check_digit != expected_check_digit:
            raise DomainValidationError("法人番号のチェックディジットが不正です。")


class InvoiceRegistrationNumber(BaseNormalizedString):
    """適格請求書発行事業者登録番号（インボイス番号、'T' + 13桁数字）。"""

    def _normalize(self, value: str) -> str:
        if isinstance(value, str):
            normalized = value.translate(
                str.maketrans("０１２３４５６７８９ｔＴ", "0123456789TT")
            )
            return re.sub(r"[\-\sー−]", "", normalized).upper()
        return value

    def validate(self) -> None:
        if not self.value:
            raise DomainValidationError(
                "適格請求書発行事業者登録番号は空にできません。"
            )
        if not re.fullmatch(r"T[0-9]{13}", self.value):
            raise DomainValidationError(
                "適格請求書発行事業者登録番号は'T'で始まる半角英数字14桁で入力してください。"
            )

    def matches_corporate_number(self, corporate_number: CorporateNumber) -> bool:
        """法人番号と一致しているか判定する。"""
        return self.value[1:] == corporate_number.value


class CorporatePostalCode(BasePostalCode):
    """法人の登記上郵便番号。"""


class CorporateAddressLine(BaseAddress):
    """法人の登記上住所本文。"""


class CorporatePhoneNumber(BaseTelephoneNumber):
    """法人の代表電話番号。"""

    field_name = "代表電話番号"


class CorporateEmailAddress(BaseEmailAddress):
    """法人の代表連絡先メールアドレス。"""


class CorporateName(BaseNormalizedString):
    """法人名"""

    def validate(self) -> None:
        if not self.value:
            raise DomainValidationError("法人名は空にできません。")
        if len(self.value) > 100:
            raise DomainValidationError("法人名は100文字以内で指定してください。")


class CorporateSearchText(BaseNormalizedString):
    """法人名称の検索文字列。"""

    def validate(self) -> None:
        if not self.value:
            raise DomainValidationError("値は空にできません。")


class CorporatePageSize(BasePositiveInt):
    """法人検索で取得する件数。"""
