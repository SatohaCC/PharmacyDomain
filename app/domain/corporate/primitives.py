"""法人（`corporate`）コンテキストの識別子・属性プリミティブ。

他の集約のIDや属性と型レベルで混同しないよう、それぞれを別型で包む。
"""

from enum import StrEnum

from app.base.domain.exceptions import DomainValidationError
from app.base.domain.primitives.primitives import (
    BaseNormalizedString,
    EntityUUID,
)
from app.base.domain.value_object import PersonName


class CorporateId(EntityUUID):
    """法人の一意識別子（UUIDv7）"""

    identifier_name = "法人ID"


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
