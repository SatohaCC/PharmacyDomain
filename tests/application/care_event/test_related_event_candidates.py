"""Event関連候補の認可と公開情報を検証する。"""

from dataclasses import fields
from datetime import UTC, datetime, timedelta

import pytest

from app.application.access_control.store_access import StoreOperation
from app.application.care_event.list_related_candidates import (
    ListRelatedEventCandidatesQuery,
    RelatedEventCandidateDto,
)
from app.domain.care_event.event import Event
from app.domain.care_event.primitives import (
    EventCreatedTimestamp,
    EventId,
    EventOccurredTimestamp,
    EventTypeId,
    EventTypeName,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientId
from app.domain.store.primitives import StoreId
from tests.application.care_event.helpers import EventFixture, create_fixture


def _event(
    *,
    corporate_id: CorporateId,
    patient_id: PatientId,
    store_id: StoreId,
    created_at: datetime,
) -> Event:
    """候補一覧用のEventを作る。"""
    return Event(
        id=EventId.generate(),
        event_type_id=EventTypeId.generate(),
        event_type_name=EventTypeName("来局相談"),
        corporate_id=corporate_id,
        patient_id=patient_id,
        store_id=store_id,
        occurred_at=EventOccurredTimestamp(created_at - timedelta(hours=1)),
        created_at=EventCreatedTimestamp(created_at),
    )


def _query(fixture: EventFixture) -> ListRelatedEventCandidatesQuery:
    """Fixtureの許可店舗と患者を対象にする。"""
    return ListRelatedEventCandidatesQuery(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        patient_id=str(fixture.patient_id.value),
    )


async def test_tc45_14_関連候補は同一法人患者の最小限のEvent情報だけを返す() -> None:
    fixture = create_fixture()
    first = _event(
        corporate_id=fixture.corporate_id,
        patient_id=fixture.patient_id,
        store_id=fixture.store_id,
        created_at=datetime(2026, 9, 1, tzinfo=UTC),
    )
    cross_store = _event(
        corporate_id=fixture.corporate_id,
        patient_id=fixture.patient_id,
        store_id=StoreId.generate(),
        created_at=datetime(2026, 9, 2, tzinfo=UTC),
    )
    await fixture.event_repository.save(first)
    await fixture.event_repository.save(cross_store)
    await fixture.event_repository.save(
        _event(
            corporate_id=fixture.corporate_id,
            patient_id=PatientId.generate(),
            store_id=fixture.store_id,
            created_at=datetime(2026, 9, 3, tzinfo=UTC),
        )
    )
    await fixture.event_repository.save(
        _event(
            corporate_id=CorporateId.generate(),
            patient_id=fixture.patient_id,
            store_id=fixture.store_id,
            created_at=datetime(2026, 9, 4, tzinfo=UTC),
        )
    )

    candidates = await fixture.list_related_candidates.execute(_query(fixture))
    cross_store_occurred_at = cross_store.occurred_at

    assert [item.event_id for item in candidates] == [
        str(cross_store.id.value),
        str(first.id.value),
    ]
    assert candidates[0].store_id == str(cross_store.store_id.value)
    assert candidates[0].event_type_name == cross_store.event_type_name.value
    assert cross_store_occurred_at is not None
    assert candidates[0].occurred_at == cross_store_occurred_at.value.isoformat()
    assert candidates[0].occurred_at_is_unknown is False
    assert candidates[0].created_at == cross_store.created_at.value.isoformat()
    assert fixture.event_repository.related_candidate_list_calls == [
        (fixture.corporate_id, fixture.patient_id)
    ]
    assert {field.name for field in fields(RelatedEventCandidateDto)} == {
        "event_id",
        "store_id",
        "event_type_name",
        "occurred_at",
        "occurred_at_is_unknown",
        "created_at",
    }


async def test_tc45_14_拒否された店舗では関連候補を検索しない() -> None:
    denied = create_fixture()
    denied.store_operations.failures[(denied.corporate_id, denied.store_id)] = (
        RuntimeError("店舗の読取が許可されていません")
    )
    with pytest.raises(RuntimeError, match="読取"):
        await denied.list_related_candidates.execute(_query(denied))

    assert denied.event_repository.related_candidate_list_calls == []
    assert denied.store_operations.calls == [
        (denied.corporate_id, denied.store_id, StoreOperation.READ_HISTORY)
    ]
