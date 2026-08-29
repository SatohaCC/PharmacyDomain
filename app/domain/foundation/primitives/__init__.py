"""具象Domain Primitiveの継承元となる基底クラス群。"""

from app.domain.foundation.primitives.base import DomainPrimitive
from app.domain.foundation.primitives.primitives import (
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
    "BasePositiveDecimal",
    "BasePositiveInt",
    "BasePostalCode",
    "BaseTelephoneNumber",
    "DomainPrimitive",
    "EntityStringId",
    "EntityUUID",
    "ensure_digits",
]
