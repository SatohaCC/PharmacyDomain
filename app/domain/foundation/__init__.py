"""各Domainコンテキストを支えるモデリング基盤。"""

from app.domain.foundation.entity import AggregateRoot, Entity
from app.domain.foundation.exceptions import DomainError, DomainValidationError
from app.domain.foundation.primitives import (
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
    DomainPrimitive,
    EntityStringId,
    EntityUUID,
    ensure_digits,
)
from app.domain.foundation.value_object import ValueObject

__all__ = [
    "AggregateRoot",
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
    "DomainError",
    "DomainPrimitive",
    "DomainValidationError",
    "Entity",
    "EntityStringId",
    "EntityUUID",
    "ValueObject",
    "ensure_digits",
]
