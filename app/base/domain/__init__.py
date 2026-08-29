"""Shared Kernel のドメイン層（例外の基底とドメインプリミティブの基底）。"""

from app.base.domain.entity import AggregateRoot, Entity
from app.base.domain.exceptions import DomainError, DomainValidationError
from app.base.domain.primitives import (
    BaseAddress,
    BaseAwareTimestamp,
    BaseDate,
    BaseEmailAddress,
    BaseFreeText,
    BaseNonNegativeDecimal,
    BaseNonNegativeInt,
    BaseNormalizedString,
    BasePersonName,
    BasePersonNameKana,
    BasePositiveDecimal,
    BasePositiveInt,
    BasePostalCode,
    BaseTelephoneNumber,
    DomainPrimitive,
    EntityStringId,
    EntityUUID,
    PersonNameKanaPart,
    PersonNamePart,
)
from app.base.domain.value_object import ValueObject

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
    "BasePersonName",
    "BasePersonNameKana",
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
    "PersonNameKanaPart",
    "PersonNamePart",
    "ValueObject",
    "ensure_digits",
]
