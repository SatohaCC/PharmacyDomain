"""Applicationのcreate_eventを定義する。"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.care_event.entities import Event


@dataclass(frozen=True, kw_only=True)
class EventDto:
    """Eventと薬歴の有無を返すDTO。"""

    event_id: str
    medication_history_id: str | None
    event_type_id: str
    event_type_name: str
    corporate_id: str
    store_id: str
    patient_id: str
    occurred_at: str | None
    occurred_at_is_unknown: bool
    created_at: str
    related_event_id: str | None
    reception_id: str | None
    prescription_id: str | None
    dispensing_id: str | None

    @classmethod
    def from_entity(
        cls, event: Event, *, medication_history_id: str | None = None
    ) -> EventDto:
        """Eventを公開用のメタデータDTOへ変換する。"""
        return cls(
            event_id=str(event.id.value),
            medication_history_id=medication_history_id,
            event_type_id=str(event.event_type_id.value),
            event_type_name=event.event_type_name.value,
            corporate_id=str(event.corporate_id.value),
            store_id=str(event.store_id.value),
            patient_id=str(event.patient_id.value),
            occurred_at=event.occurred_at.value.isoformat()
            if event.occurred_at is not None
            else None,
            occurred_at_is_unknown=event.occurred_at_is_unknown,
            created_at=event.created_at.value.isoformat(),
            related_event_id=str(event.related_event_id.value)
            if event.related_event_id is not None
            else None,
            reception_id=str(event.reception_id.value)
            if event.reception_id is not None
            else None,
            prescription_id=str(event.prescription_id.value)
            if event.prescription_id is not None
            else None,
            dispensing_id=str(event.dispensing_id.value)
            if event.dispensing_id is not None
            else None,
        )
