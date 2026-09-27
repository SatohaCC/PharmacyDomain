"""業務Eventの作成と参照境界。"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.application.access_control.exceptions import TenantBoundaryNotFoundError
from app.application.access_control.models import ActorRole
from app.application.access_control.store_access import StoreOperation
from app.application.common.exceptions import AuthorizationError
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
from tests.application.care_event.helpers import create_command, create_fixture


def _existing_event(
    *,
    corporate_id: CorporateId,
    patient_id: PatientId,
    store_id: StoreId,
) -> Event:
    occurred_at = datetime(2026, 8, 1, 2, 0, tzinfo=UTC)
    return Event(
        id=EventId.generate(),
        event_type_id=EventTypeId.generate(),
        event_type_name=EventTypeName("来局相談"),
        corporate_id=corporate_id,
        patient_id=patient_id,
        store_id=store_id,
        occurred_at=EventOccurredTimestamp(occurred_at),
        created_at=EventCreatedTimestamp(occurred_at),
    )


async def test_tc45_09_17_Eventは薬歴や処方調剤なしで作成できる() -> None:
    fixture = create_fixture()

    created = await fixture.create_event.execute(create_command(fixture))

    saved = fixture.event_repository.items[EventId.parse(created.event_id)]
    assert created.medication_history_id is None
    assert saved.prescription_id is None
    assert saved.dispensing_id is None
    assert saved.reception_id is None


async def test_tc45_05_無効種別で新規Eventを作成できない() -> None:
    fixture = create_fixture()
    active = fixture.event_definition_repository.items[fixture.event_type_id]
    inactive = Event(
        id=EventId.generate(),
        event_type_id=fixture.event_type_id,
        event_type_name=active.name,
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        patient_id=fixture.patient_id,
        occurred_at=EventOccurredTimestamp(datetime(2026, 8, 1, tzinfo=UTC)),
        created_at=EventCreatedTimestamp(datetime(2026, 9, 26, tzinfo=UTC)),
    )
    await fixture.event_repository.save(inactive)
    await fixture.event_definition_repository.save(
        EventDefinition(
            id=active.id,
            name=active.name,
            corporate_id=active.corporate_id,
            standard_code=active.standard_code,
            is_active=False,
        )
    )

    with pytest.raises(DomainError):
        await fixture.create_event.execute(create_command(fixture))

    assert len(fixture.event_repository.items) == 1


async def test_tc45_10_Event実施日時と登録日時は別の値を保持する() -> None:
    fixture = create_fixture()
    occurred_at = datetime(2026, 8, 1, 3, 0, tzinfo=UTC)

    created = await fixture.create_event.execute(
        create_command(fixture, occurred_at=occurred_at)
    )

    saved = fixture.event_repository.items[EventId.parse(created.event_id)]
    saved_occurred_at = saved.occurred_at
    assert saved_occurred_at is not None
    assert saved_occurred_at.value == occurred_at
    assert saved.created_at.value == fixture.clock.now()
    assert saved.created_at.value != saved_occurred_at.value


async def test_tc45_13_同一患者の別店舗Eventを関連元にできる() -> None:
    fixture = create_fixture()
    related = _existing_event(
        corporate_id=fixture.corporate_id,
        patient_id=fixture.patient_id,
        store_id=StoreId.generate(),
    )
    await fixture.event_repository.save(related)

    created = await fixture.create_event.execute(
        create_command(fixture, related_event_id=str(related.id.value))
    )

    saved = fixture.event_repository.items[EventId.parse(created.event_id)]
    assert saved.related_event_id == related.id
    assert saved.store_id == fixture.store_id
    assert related.store_id != saved.store_id


@pytest.mark.parametrize("wrong_scope", ["corporate", "patient", "missing"])
async def test_tc45_15_別法人_別患者_存在しないEventを関連元にできない(
    wrong_scope: str,
) -> None:
    fixture = create_fixture()
    if wrong_scope == "missing":
        with pytest.raises(TenantBoundaryNotFoundError):
            await fixture.create_event.execute(
                create_command(
                    fixture,
                    related_event_id=str(EventId.generate().value),
                )
            )

        assert fixture.event_repository.items == {}
        return

    related = _existing_event(
        corporate_id=(
            CorporateId.generate()
            if wrong_scope == "corporate"
            else fixture.corporate_id
        ),
        patient_id=(
            PatientId.generate() if wrong_scope == "patient" else fixture.patient_id
        ),
        store_id=fixture.store_id,
    )
    await fixture.event_repository.save(related)

    with pytest.raises(TenantBoundaryNotFoundError):
        await fixture.create_event.execute(
            create_command(fixture, related_event_id=str(related.id.value))
        )

    assert len(fixture.event_repository.items) == 1


async def test_tc45_20_Event作成は_CREATE_EVENTの店舗業務境界を通る() -> None:
    fixture = create_fixture()

    await fixture.create_event.execute(
        create_command(
            fixture,
            occurred_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
    )

    assert fixture.store_operations.calls == [
        (fixture.corporate_id, fixture.store_id, StoreOperation.CREATE_EVENT)
    ]


async def test_tc45_06_店舗閲覧者はEventを作成できない() -> None:
    fixture = create_fixture(role=ActorRole.STORE_VIEWER)

    with pytest.raises(AuthorizationError):
        await fixture.create_event.execute(create_command(fixture))

    assert fixture.event_repository.items == {}


async def test_tc45_15_法人に属さない患者のEventを作成できない() -> None:
    fixture = create_fixture()
    unknown_patient_id = PatientId.generate()

    with pytest.raises(TenantBoundaryNotFoundError):
        await fixture.create_event.execute(
            create_command(fixture, patient_id=unknown_patient_id)
        )

    assert fixture.event_repository.items == {}


async def test_tc45_20_店舗業務境界が拒否したEventを保存しない() -> None:
    fixture = create_fixture()
    failure = RuntimeError("店舗が新規業務を受け付けない")
    fixture.store_operations.failures[(fixture.corporate_id, fixture.store_id)] = (
        failure
    )

    with pytest.raises(RuntimeError, match="新規業務"):
        await fixture.create_event.execute(create_command(fixture))

    assert fixture.event_repository.items == {}
