"""業務Eventの日時・ID・関連参照の不変条件。"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.domain.care_event.event import Event
from app.domain.care_event.event_definition import EventDefinition
from app.domain.care_event.primitives import (
    EventCreatedTimestamp,
    EventId,
    EventOccurredTimestamp,
    EventTypeId,
    EventTypeName,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.foundation.exceptions import DomainError
from app.domain.patient.primitives import PatientId
from app.domain.store.primitives import StoreId


def _event(*, occurred_at: datetime) -> Event:
    return Event.create(
        event_type_id=EventTypeId.generate(),
        event_type_name=EventTypeName("来局相談"),
        corporate_id=CorporateId.generate(),
        store_id=StoreId.generate(),
        patient_id=PatientId.generate(),
        occurred_at=EventOccurredTimestamp(occurred_at),
        created_at=EventCreatedTimestamp(datetime(2026, 9, 26, 3, 0, tzinfo=UTC)),
    )


def test_tc45_10_Eventの登録時刻と発生時刻は分離して保持する() -> None:
    occurred_at = datetime(2026, 8, 1, 2, 0, tzinfo=UTC)

    event = _event(occurred_at=occurred_at)
    event_occurred_at = event.occurred_at

    assert event.id.value.version == 7
    assert event.created_at.value == datetime(2026, 9, 26, 3, 0, tzinfo=UTC)
    assert event_occurred_at is not None
    assert event_occurred_at.value == occurred_at
    assert event.created_at.value != event_occurred_at.value


def test_tc45_11_タイムゾーンのない発生日時を拒否する() -> None:
    with pytest.raises(DomainError):
        EventOccurredTimestamp(datetime(2026, 8, 1, 2, 0))  # noqa: DTZ001


def test_tc45_16_Eventの自己参照を拒否する() -> None:
    event_id = EventId.generate()

    with pytest.raises(DomainError):
        Event(
            id=event_id,
            event_type_id=EventTypeId.generate(),
            event_type_name=EventTypeName("来局相談"),
            corporate_id=CorporateId.generate(),
            store_id=StoreId.generate(),
            patient_id=PatientId.generate(),
            occurred_at=EventOccurredTimestamp(datetime(2026, 8, 1, tzinfo=UTC)),
            created_at=EventCreatedTimestamp(datetime(2026, 9, 26, tzinfo=UTC)),
            related_event_id=event_id,
        )


def test_tc45_05_Eventは作成時点の種別名を表示用に保持する() -> None:
    corporate_id = CorporateId.generate()
    definition = EventDefinition(
        id=EventTypeId.generate(),
        name=EventTypeName("服薬期間中フォローアップ"),
        corporate_id=corporate_id,
    )
    event = Event(
        id=EventId.generate(),
        event_type_id=definition.id,
        event_type_name=definition.name,
        corporate_id=corporate_id,
        store_id=StoreId.generate(),
        patient_id=PatientId.generate(),
        occurred_at=EventOccurredTimestamp(datetime(2026, 8, 1, tzinfo=UTC)),
        created_at=EventCreatedTimestamp(datetime(2026, 9, 26, tzinfo=UTC)),
    )

    renamed = definition.rename(EventTypeName("服薬後の相談"))

    assert renamed.name.value == "服薬後の相談"
    assert event.event_type_name.value == "服薬期間中フォローアップ"


def test_tc45_17_処方と調剤なしで相談Eventを作れる() -> None:
    event = _event(occurred_at=datetime(2026, 8, 1, tzinfo=UTC))

    assert event.prescription_id is None
    assert event.dispensing_id is None
    assert event.reception_id is None
