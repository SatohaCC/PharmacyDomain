"""コンテキスト横断で使う値オブジェクトの基底クラス群。"""

from app.base.domain.primitives.base import DomainPrimitive
from app.base.domain.primitives.person_primitives import (
    BasePersonName,
    BasePersonNameKana,
    PersonNameKanaPart,
    PersonNamePart,
)
from app.base.domain.primitives.primitives import (
    BaseAddress,
    BaseAwareTimestamp,
    BaseDate,
    BaseEmailAddress,
    BaseFreeText,
    BaseNonNegativeDecimal,
    BaseNonNegativeInt,
    BaseNormalizedString,
    BasePositiveDecimal,
    BasePositiveInt,
    BasePostalCode,
    BaseTelephoneNumber,
    EntityStringId,
    EntityUUID,
    ensure_digits,
)

__all__ = [
    "BaseAddress",
    "BaseAwareTimestamp",
    "BaseDate",
    "BaseEmailAddress",
    "BaseFreeText",
    "BaseNonNegativeDecimal",
    "BaseNonNegativeInt",
    "BaseNormalizedString",
    "BasePersonName",
    "BasePersonNameKana",
    "BasePositiveDecimal",
    "BasePositiveInt",
    "BasePostalCode",
    "BaseTelephoneNumber",
    "DomainPrimitive",
    "EntityStringId",
    "EntityUUID",
    "PersonNameKanaPart",
    "PersonNamePart",
    "ensure_digits",
]
