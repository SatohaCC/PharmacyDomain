"""コンテキスト横断で使う値オブジェクトの基底クラス群。"""

from app.base.domain.primitives.base import DomainPrimitive
from app.base.domain.primitives.person_primitives import (
    BasePersonName,
    BasePersonNameKana,
)
from app.base.domain.primitives.primitives import (
    BaseAddress,
    BaseDate,
    BaseEmailAddress,
    BaseFreeText,
    BaseNonNegativeFloat,
    BaseNonNegativeInt,
    BaseNormalizedString,
    BasePositiveFloat,
    BasePositiveInt,
    BasePostalCode,
    BaseTelephoneNumber,
    EntityStringId,
    EntityUUID,
)

__all__ = [
    "BaseAddress",
    "BaseDate",
    "BaseEmailAddress",
    "BaseFreeText",
    "BaseNonNegativeFloat",
    "BaseNonNegativeInt",
    "BaseNormalizedString",
    "BasePersonName",
    "BasePersonNameKana",
    "BasePositiveFloat",
    "BasePositiveInt",
    "BasePostalCode",
    "BaseTelephoneNumber",
    "DomainPrimitive",
    "EntityStringId",
    "EntityUUID",
]
