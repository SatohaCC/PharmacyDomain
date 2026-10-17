"""法人（`corporate`）コンテキストの識別子・属性プリミティブ。

他の集約のIDや属性と型レベルで混同しないよう、それぞれを別型で包む。
"""

from enum import StrEnum

from app.domain.foundation.exceptions import DomainValidationError
from app.domain.foundation.primitives.primitives import BaseNormalizedString
from app.domain.shared.person_name import PersonName


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


class CorporateRepresentativeName(PersonName):
    """代表者名"""
