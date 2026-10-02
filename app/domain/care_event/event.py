"""患者に対する調剤・服薬指導・来局・フォローアップ等の薬局業務イベント履歴を管理するモジュール。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Self

from app.domain.care_event.primitives import (
    EventCreatedTimestamp,
    EventId,
    EventOccurredTimestamp,
    EventTypeId,
    EventTypeName,
    EventTypeStandardCode,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing.primitives import DispensingId
from app.domain.foundation.entity import AggregateRoot
from app.domain.foundation.exceptions import DomainError
from app.domain.patient.primitives import PatientId
from app.domain.prescription.primitives import PrescriptionId
from app.domain.reception.primitives import ReceptionId
from app.domain.store.primitives import StoreId


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
