"""corporateの単一値と列挙・検証規則。"""

from __future__ import annotations

from enum import StrEnum

from app.domain.foundation.exceptions import DomainValidationError
from app.domain.foundation.primitives.primitives import (
    BaseNormalizedString,
    BasePositiveInt,
)


class CorporateStatus(StrEnum):
    """法人の利用状態。"""

    ACTIVE = "active"
    INACTIVE = "inactive"


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
