"""care_eventのエンティティと集約。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Self

from app.domain.care_event.identifiers import EventId, EventTypeId
from app.domain.care_event.primitives import (
    EventCreatedTimestamp,
    EventOccurredTimestamp,
    EventTypeName,
    EventTypeStandardCode,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.dispensing.identifiers import DispensingId
from app.domain.foundation.entity import AggregateRoot
from app.domain.foundation.exceptions import DomainError
from app.domain.patient.identifiers import PatientId
from app.domain.prescription.identifiers import PrescriptionId
from app.domain.reception.identifiers import ReceptionId
from app.domain.store.identifiers import StoreId


@dataclass(frozen=True, eq=False, kw_only=True)
class Event(AggregateRoot[EventId]):
    """患者に対して発生した1件の業務イベント（来局受付、調剤、服薬指導、電話フォローアップ、トレーシングレポート等）。"""

    id: EventId
    event_type_id: EventTypeId
    event_definition_corporate_id: CorporateId | None = None
    event_type_standard_code: EventTypeStandardCode | None = None
    event_type_name: EventTypeName
    corporate_id: CorporateId
    store_id: StoreId
    patient_id: PatientId
    occurred_at: EventOccurredTimestamp | None
    created_at: EventCreatedTimestamp
    related_event_id: EventId | None = None
    reception_id: ReceptionId | None = None
    prescription_id: PrescriptionId | None = None
    dispensing_id: DispensingId | None = None

    def validate(self) -> None:
        """Event単体で守れる参照整合性を検証する。"""
        if (
            self.event_definition_corporate_id is not None
            and self.event_definition_corporate_id != self.corporate_id
        ):
            raise DomainError("Event種別は標準または同一法人の定義に限ります。")
        if self.related_event_id == self.id:
            raise DomainError("Eventは自分自身を関連元にできません。")

    @property
    def occurred_at_is_unknown(self) -> bool:
        """移行元から発生日時を確定できなかった記録かを返す。"""
        return self.occurred_at is None

    def resolve_unknown_occurrence(self, occurred_at: EventOccurredTimestamp) -> Event:
        """時刻不明で移行したEventに、確認済みの発生日時を一度だけ設定する。"""
        if self.occurred_at is not None:
            raise DomainError("Eventの発生日時は一度設定した後に変更できません。")
        return replace(self, occurred_at=occurred_at)

    @classmethod
    def create(
        cls,
        *,
        event_type_id: EventTypeId,
        event_definition_corporate_id: CorporateId | None = None,
        event_type_standard_code: EventTypeStandardCode | None = None,
        event_type_name: EventTypeName,
        corporate_id: CorporateId,
        store_id: StoreId,
        patient_id: PatientId,
        occurred_at: EventOccurredTimestamp,
        created_at: EventCreatedTimestamp,
        related_event_id: EventId | None = None,
        reception_id: ReceptionId | None = None,
        prescription_id: PrescriptionId | None = None,
        dispensing_id: DispensingId | None = None,
    ) -> Self:
        return cls(
            id=EventId.generate(),
            event_type_id=event_type_id,
            event_definition_corporate_id=event_definition_corporate_id,
            event_type_standard_code=event_type_standard_code,
            event_type_name=event_type_name,
            corporate_id=corporate_id,
            store_id=store_id,
            patient_id=patient_id,
            occurred_at=occurred_at,
            created_at=created_at,
            related_event_id=related_event_id,
            reception_id=reception_id,
            prescription_id=prescription_id,
            dispensing_id=dispensing_id,
        )


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
