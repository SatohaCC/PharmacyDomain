"""薬歴とEventを一緒に保存するPostgreSQL結合テスト用ヘルパー。"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String, column, table
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.elements import ColumnClause
from sqlalchemy.sql.selectable import TableClause

from app.domain.care_event.event import Event
from app.domain.care_event.event_definition import EventDefinition
from app.domain.care_event.primitives import (
    EventCreatedTimestamp,
    EventOccurredTimestamp,
)
from app.domain.medication_history.medication_history_record import (
    MedicationHistoryRecord,
)
from app.infrastructure.postgres.repositories.repository_set import (
    PostgresRepositorySet,
)
from tests.factories.dispensing_factory import create_dispensing
from tests.factories.prescription_factory import create_prescription


async def save_history_event(
    repositories: PostgresRepositorySet, record: MedicationHistoryRecord
) -> Event:
    """薬歴のEvent参照先を作成して保存する。"""
    if record.prescription_id is not None:
        prescription = await repositories.prescription.get(
            corporate_id=record.corporate_id,
            prescription_id=record.prescription_id,
        )
        if prescription is None:
            created = create_prescription(
                corporate_id=record.corporate_id,
                store_id=record.store_id,
                patient_id=record.patient_id,
                document_number=record.id.value.hex[:16],
            )
            await repositories.prescription.save(
                replace(created, id=record.prescription_id)
            )
    if record.dispensing_id is not None:
        if record.prescription_id is None:
            raise AssertionError("調剤参照のある薬歴には処方箋参照が必要です")
        dispensing = await repositories.dispensing.get(
            corporate_id=record.corporate_id,
            dispensing_id=record.dispensing_id,
        )
        if dispensing is None:
            created_process = create_dispensing(
                corporate_id=record.corporate_id,
                store_id=record.store_id,
                patient_id=record.patient_id,
                prescription_id=record.prescription_id,
            )
            await repositories.dispensing.save(
                replace(created_process, id=record.dispensing_id)
            )

    definitions = await repositories.event_definition.list_for_corporate(
        corporate_id=record.corporate_id
    )
    standard_code = (
        "medication_period_follow_up"
        if record.dispensing_id is None
        else "prescription_reception"
    )
    definition: EventDefinition | None = next(
        (
            item
            for item in definitions
            if item.corporate_id is None
            and item.standard_code is not None
            and item.standard_code.value == standard_code
        ),
        None,
    )
    if definition is None:
        raise AssertionError(f"標準Event種別が見つかりません: {standard_code}")

    event = Event(
        id=record.event_id,
        event_type_id=definition.id,
        event_type_standard_code=definition.standard_code,
        event_type_name=definition.name,
        corporate_id=record.corporate_id,
        store_id=record.store_id,
        patient_id=record.patient_id,
        occurred_at=(
            None
            if record.counseled_at is None
            else EventOccurredTimestamp(record.counseled_at.value)
        ),
        created_at=EventCreatedTimestamp(datetime(2026, 9, 20, tzinfo=UTC)),
        prescription_id=record.prescription_id,
        dispensing_id=record.dispensing_id,
    )
    await repositories.event.save(event)
    return event


async def save_history_with_event(
    repositories: PostgresRepositorySet, record: MedicationHistoryRecord
) -> None:
    """薬歴のEventを先に保存し、薬歴を保存する。"""
    await save_history_event(repositories, record)
    await repositories.medication_history.save(record)


def legacy_medication_history_table(
    *, has_record_kind: bool, has_recorded_at: bool
) -> TableClause:
    """対象migration直前の薬歴列を持つ一時テーブル記述を作る。"""
    columns: list[ColumnClause[Any]] = [
        column("id", postgresql.UUID(as_uuid=True)),
        column("corporate_id", postgresql.UUID(as_uuid=True)),
        column("store_id", postgresql.UUID(as_uuid=True)),
        column("patient_id", postgresql.UUID(as_uuid=True)),
        column("dispensing_id", postgresql.UUID(as_uuid=True)),
        column("prescription_id", postgresql.UUID(as_uuid=True)),
    ]
    if has_record_kind:
        columns.extend(
            (
                column("record_kind", String(length=32)),
                column("source_record_id", postgresql.UUID(as_uuid=True)),
            )
        )
    columns.extend(
        (
            column("status", String(length=32)),
            column("counseled_at", DateTime(timezone=True)),
        )
    )
    if has_recorded_at:
        columns.append(column("recorded_at", DateTime(timezone=True)))
    columns.extend(
        (
            column("payload", postgresql.JSONB()),
            column("version", Integer()),
            column("created_at", DateTime(timezone=True)),
            column("updated_at", DateTime(timezone=True)),
        )
    )
    return table("medication_history_records", *columns)
