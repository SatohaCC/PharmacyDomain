"""時刻不明で移行したEventの確定境界。"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app.application.composition.medication_history_references import (
    MedicationHistoryEventOccurrenceAdapter,
)
from app.application.medication_history.finalize_medication_history import (
    FinalizeMedicationHistoryCommand,
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
from app.domain.foundation.exceptions import DomainError
from app.domain.medication_history.exceptions import MedicationHistoryDomainError
from app.domain.medication_history.primitives import (
    MedicationHistoryRecordId,
    MedicationHistoryStatus,
)
from app.domain.patient.primitives import PatientId
from app.domain.store.primitives import StoreId
from tests.application.medication_history.helpers import (
    create_fixture,
    create_start_command,
)
from tests.fakes.in_memory_event_repository import InMemoryEventRepository


def _時刻不明イベント() -> Event:
    登録日時 = datetime(2026, 9, 20, 1, tzinfo=UTC)
    return Event(
        id=EventId.generate(),
        event_type_id=EventTypeId.generate(),
        event_type_name=EventTypeName("処方箋受付"),
        corporate_id=CorporateId.generate(),
        store_id=StoreId.generate(),
        patient_id=PatientId.generate(),
        occurred_at=None,
        created_at=EventCreatedTimestamp(登録日時),
    )


async def test_tc45_53_時刻不明Eventは確認日時なしで確定できず一度だけ更新される() -> (
    None
):
    event = _時刻不明イベント()
    repository = InMemoryEventRepository()
    await repository.save(event)
    adapter = MedicationHistoryEventOccurrenceAdapter(repository)

    with pytest.raises(MedicationHistoryDomainError, match="確認済みの発生日時"):
        await adapter.resolve_unknown_occurrence(
            corporate_id=event.corporate_id,
            event_id=event.id,
            occurred_at=None,
        )

    assert await repository.get(corporate_id=event.corporate_id, event_id=event.id)
    stored = await repository.get(corporate_id=event.corporate_id, event_id=event.id)
    assert stored is not None
    assert stored.occurred_at is None

    confirmed_at = datetime(2026, 9, 12, 2, tzinfo=UTC)
    await adapter.resolve_unknown_occurrence(
        corporate_id=event.corporate_id,
        event_id=event.id,
        occurred_at=confirmed_at,
    )
    stored = await repository.get(corporate_id=event.corporate_id, event_id=event.id)
    assert stored is not None
    assert stored.occurred_at == EventOccurredTimestamp(confirmed_at)
    assert stored.created_at == event.created_at

    with pytest.raises(MedicationHistoryDomainError, match="変更できません"):
        await adapter.resolve_unknown_occurrence(
            corporate_id=event.corporate_id,
            event_id=event.id,
            occurred_at=datetime(2026, 9, 13, 2, tzinfo=UTC),
        )
    with pytest.raises(DomainError, match="一度設定した後に変更できません"):
        stored.resolve_unknown_occurrence(
            EventOccurredTimestamp(datetime(2026, 9, 13, 2, tzinfo=UTC))
        )


async def test_tc45_53_薬歴確定は時刻不明Eventへ確認時刻を明示要求する() -> None:
    fixture = create_fixture()
    command = create_start_command(fixture)
    event_id = EventId.parse(command.event_id)
    unknown_event = replace(fixture.event_repository.items[event_id], occurred_at=None)
    fixture.event_repository.items[event_id] = unknown_event
    draft = await fixture.start.execute(command)
    fixture.finalize._event_occurrence = MedicationHistoryEventOccurrenceAdapter(
        fixture.event_repository
    )
    finalize_command = FinalizeMedicationHistoryCommand(
        corporate_id=draft.corporate_id,
        record_id=draft.id,
        review_result="assessment_and_instruction_recorded",
    )

    with pytest.raises(MedicationHistoryDomainError, match="確認済みの発生日時"):
        await fixture.finalize.execute(finalize_command)

    stored_draft = await fixture.record_repository.get(
        corporate_id=fixture.corporate_id,
        record_id=MedicationHistoryRecordId.parse(draft.id),
    )
    stored_event = await fixture.event_repository.get(
        corporate_id=fixture.corporate_id, event_id=event_id
    )
    assert stored_draft is not None
    assert stored_draft.status is MedicationHistoryStatus.DRAFT
    assert stored_event is not None and stored_event.occurred_at is None
    assert fixture.profile_repository.items == {}

    confirmed_at = datetime(2026, 9, 12, 2, tzinfo=UTC)
    finalized = await fixture.finalize.execute(
        FinalizeMedicationHistoryCommand(
            corporate_id=draft.corporate_id,
            record_id=draft.id,
            review_result="assessment_and_instruction_recorded",
            event_occurred_at=confirmed_at,
        )
    )

    stored_event = await fixture.event_repository.get(
        corporate_id=fixture.corporate_id, event_id=event_id
    )
    assert finalized.status == MedicationHistoryStatus.FINALIZED.value
    assert stored_event is not None
    assert stored_event.occurred_at == EventOccurredTimestamp(confirmed_at)
    assert finalized.counseled_at == fixture.clock.now().isoformat()
