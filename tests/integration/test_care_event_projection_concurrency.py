"""薬歴確定の同時実行後も頭書きが全件から再構築できることを検証する。"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.domain.care_event.event import Event
from app.domain.care_event.primitives import (
    EventCreatedTimestamp,
    EventOccurredTimestamp,
)
from app.domain.medication_history.patient_medical_profile import (
    PatientMedicalProfile,
)
from app.domain.medication_history.primitives import MedicationHistoryRecordId
from app.domain.medication_history.value_objects import ProfileUpdateIntents
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.infrastructure.postgres.repositories.repository_set import (
    PostgresRepositorySet,
)
from tests.factories.medication_history_factory import (
    create_adverse_reaction_intent,
)
from tests.integration.test_clinical_transaction_http import (
    ClinicalFixture,
    _client,
    setup_clinical,
)


@pytest.mark.asyncio
async def test_tc45_48_同時確定は競合応答または完全な頭書き投影になる(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """競合を明示し、再試行後の頭書きが全ての確定記録と一致する。"""
    fixture: ClinicalFixture = await setup_clinical(engine, session_factory)
    occurred_at = datetime(2026, 9, 20, 4, tzinfo=UTC)

    async with PostgresUnitOfWork(session_factory) as work:
        repositories = PostgresRepositorySet.create(work)
        definitions = await repositories.event_definition.list_for_corporate(
            corporate_id=fixture.corporate_id
        )
        definition = next(
            item
            for item in definitions
            if item.corporate_id is None
            and item.standard_code is not None
            and item.standard_code.value == "in_person_consultation"
        )
        event = Event.create(
            event_type_id=definition.id,
            event_type_standard_code=definition.standard_code,
            event_type_name=definition.name,
            corporate_id=fixture.corporate_id,
            store_id=fixture.record.store_id,
            patient_id=fixture.record.patient_id,
            occurred_at=EventOccurredTimestamp(occurred_at),
            created_at=EventCreatedTimestamp(occurred_at),
        )
        second_record = replace(
            fixture.record,
            id=MedicationHistoryRecordId.generate(),
            event_id=event.id,
            prescription_id=None,
            dispensing_id=None,
            profile_updates=ProfileUpdateIntents(
                new_adverse_reactions=(create_adverse_reaction_intent(),)
            ),
        )
        await repositories.event.save(event)
        await repositories.medication_history.save(second_record)
        await work.commit()

    async def finalize(record_id: MedicationHistoryRecordId) -> httpx.Response:
        async with _client(fixture) as client:
            return await client.post(
                f"/corporates/{fixture.corporate_id.value}"
                f"/medication-histories/{record_id.value}/finalization",
                json={"review_result": "assessment_and_instruction_recorded"},
            )

    responses = await asyncio.gather(
        finalize(fixture.record.id), finalize(second_record.id)
    )
    assert all(response.status_code in {200, 409} for response in responses), [
        (response.status_code, response.text) for response in responses
    ]
    assert any(response.status_code == 200 for response in responses)

    for record_id, response in zip(
        (fixture.record.id, second_record.id), responses, strict=True
    ):
        if response.status_code == 409:
            retry = await finalize(record_id)
            assert retry.status_code == 200, retry.text

    async with PostgresUnitOfWork(session_factory) as work:
        repositories = PostgresRepositorySet.create(work)
        records = await repositories.medication_history.list_for_profile_projection(
            corporate_id=fixture.corporate_id,
            patient_id=fixture.record.patient_id,
        )
        stored_records = [
            await repositories.medication_history.get(
                corporate_id=fixture.corporate_id,
                record_id=record_id,
            )
            for record_id in (fixture.record.id, second_record.id)
        ]
        profile = await repositories.patient_medical_profile.get_by_patient(
            corporate_id=fixture.corporate_id,
            patient_id=fixture.record.patient_id,
        )

    assert all(record is not None and record.is_finalized for record in stored_records)
    assert profile is not None
    rebuilt = PatientMedicalProfile.rebuild_from(
        corporate_id=fixture.corporate_id,
        patient_id=fixture.record.patient_id,
        records=tuple(item for item in records if item.is_projection_eligible),
    )
    assert profile.allergies == rebuilt.allergies
    assert profile.adverse_reactions == rebuilt.adverse_reactions
    assert profile.medical_conditions == rebuilt.medical_conditions
    assert profile.source_record_ids == rebuilt.source_record_ids
