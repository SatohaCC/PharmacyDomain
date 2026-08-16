"""Shared Kernel のドメイン層（例外の基底とドメインプリミティブの基底）。"""

from app.base.domain.entity import AggregateRoot, Entity
from app.base.domain.exceptions import DomainError, DomainValidationError
from app.base.domain.primitives import (
    BaseAddress,
    BaseDate,
    BaseEmailAddress,
    BaseFreeText,
    BaseNonNegativeFloat,
    BaseNonNegativeInt,
    BaseNormalizedString,
    BasePersonName,
    BasePersonNameKana,
    BasePositiveFloat,
    BasePositiveInt,
    BasePostalCode,
    BaseTelephoneNumber,
    DomainPrimitive,
    EntityStringId,
    EntityUUID,
)

__all__ = [
    "AggregateRoot",
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
    "DomainError",
    "DomainPrimitive",
    "DomainValidationError",
    "Entity",
    "EntityStringId",
    "EntityUUID",
]
