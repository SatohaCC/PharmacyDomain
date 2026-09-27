"""業務イベント種別の集約。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Self

from app.domain.care_event.primitives import (
    EventTypeId,
    EventTypeName,
    EventTypeStandardCode,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.foundation.entity import AggregateRoot
from app.domain.foundation.exceptions import DomainError


@dataclass(frozen=True, eq=False, kw_only=True)
class EventDefinition(AggregateRoot[EventTypeId]):
    """標準または法人独自のイベント種別。"""

    id: EventTypeId
    name: EventTypeName
    corporate_id: CorporateId | None = None
    standard_code: EventTypeStandardCode | None = None
    is_active: bool = True

    def validate(self) -> None:
        """標準種別と法人独自種別の所有者表現を一致させる。"""
        has_standard_code = self.standard_code is not None
        if (self.corporate_id is None) != has_standard_code:
            raise DomainError("標準種別か法人独自種別のどちらかを指定してください。")
        if not self.name.value:
            raise DomainError("イベント種別名は空にできません。")
        if self.standard_code is not None and not self.standard_code.value:
            raise DomainError("標準イベント種別コードは空にできません。")

    @classmethod
    def create_custom(cls, *, corporate_id: CorporateId, name: EventTypeName) -> Self:
        return cls(id=EventTypeId.generate(), name=name, corporate_id=corporate_id)

    @classmethod
    def create_standard(
        cls, *, code: EventTypeStandardCode, name: EventTypeName
    ) -> Self:
        return cls(id=EventTypeId.generate(), name=name, standard_code=code)

    def rename(self, name: EventTypeName) -> Self:
        if self.corporate_id is None:
            raise DomainError("標準イベント種別は改名できません。")
        return type(self)(
            id=self.id,
            name=name,
            corporate_id=self.corporate_id,
            is_active=self.is_active,
        )

    def deactivate(self) -> Self:
        if self.corporate_id is None:
            raise DomainError("標準イベント種別は無効化できません。")
        if not self.is_active:
            return self
        return type(self)(
            id=self.id,
            name=self.name,
            corporate_id=self.corporate_id,
            is_active=False,
        )
