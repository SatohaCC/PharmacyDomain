"""旧薬歴のEvent化を実PostgreSQLのmigrationで検証する。"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from io import StringIO
from typing import Any, cast
from uuid import UUID

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Connection, insert, text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.domain.care_event.primitives import EventId
from app.domain.medication_history.medication_history_record import (
    MedicationHistoryRecord,
)
from app.domain.medication_history.patient_medical_profile import (
    PatientMedicalProfile,
)
from app.domain.medication_history.primitives import (
    FinalizationDelayReason,
    FinalizedTimestamp,
    FollowUpId,
    FollowUpRecordedTimestamp,
    MedicationHistoryRecordedTimestamp,
    MedicationHistoryRecordId,
    MedicationHistoryStatus,
    TracingReportId,
)
from app.domain.medication_history.value_objects import (
    FollowUpRecord,
    ProfileUpdateIntents,
)
from app.domain.reception.primitives import ReceptionId
from app.domain.staff.primitives import StaffId
from app.infrastructure.postgres import schema
from app.infrastructure.postgres.codec import decode_aggregate, encode_aggregate
from app.infrastructure.postgres.repositories.corporate import CORPORATE_MAPPING
from app.infrastructure.postgres.repositories.dispensing_process import (
    DISPENSING_PROCESS_MAPPING,
)
from app.infrastructure.postgres.repositories.medication_history import (
    MEDICATION_HISTORY_RECORD_MAPPING,
)
from app.infrastructure.postgres.repositories.patient import PATIENT_MAPPING
from app.infrastructure.postgres.repositories.prescription import (
    PRESCRIPTION_MAPPING,
)
from app.infrastructure.postgres.repositories.store import STORE_MAPPING
from app.infrastructure.postgres.repository_base import AggregateMapping
from tests.factories.dispensing_factory import create_dispensing
from tests.factories.medication_history_factory import (
    create_allergy_intent,
    create_follow_up,
    create_record,
    create_tracing_report,
    create_tracing_report_response,
    finalize_record_with_review,
)
from tests.factories.persistence_factory import create_patient
from tests.factories.prescription_factory import create_prescription
from tests.factories.store_factory import create_store
from tests.infrastructure.postgres.helpers import create_corporate, ordered_migrations
from tests.integration.medication_history_helpers import (
    legacy_medication_history_table,
)

_TARGET_REVISION = "20260927_0010"
_MIGRATED_AT = datetime(2026, 9, 20, tzinfo=UTC)


def _run_migrations(
    connection: Connection,
    *,
    operation: str,
    modules: list[Any],
) -> None:
    """同期接続でAlembic migration列を実行する。"""
    with Operations.context(MigrationContext.configure(connection=connection)):
        for module in modules:
            getattr(module, operation)()


def _prepare_preceding_schema(connection: Connection) -> Any:
    """対象migration直前までの実スキーマを作る。"""
    schema.metadata.drop_all(connection, checkfirst=True)
    modules = ordered_migrations()
    target = next(
        module for module in modules if str(module.revision) == _TARGET_REVISION
    )
    _run_migrations(
        connection,
        operation="upgrade",
        modules=modules[: modules.index(target)],
    )
    return target


def _aggregate_row[AggregateT](
    mapping: AggregateMapping[AggregateT], aggregate: AggregateT
) -> dict[str, object]:
    """旧スキーマにも共通する集約の列とJSON payloadを作る。"""
    values = mapping.row_values(aggregate)
    values.update(version=1, created_at=_MIGRATED_AT, updated_at=_MIGRATED_AT)
    return values


def _legacy_record_values(
    record: MedicationHistoryRecord,
    *,
    record_kind: str,
    source_record_id: UUID | None,
    follow_ups: tuple[dict[str, object], ...] = (),
    tracing_reports: tuple[dict[str, object], ...] = (),
) -> dict[str, object]:
    """migration直前の独立薬歴列とpayloadを組み立てる。"""
    payload = encode_aggregate(record)
    payload.pop("event_id", None)
    payload.update(
        record_kind=record_kind,
        source_record_id=(
            str(source_record_id) if source_record_id is not None else None
        ),
        follow_ups=list(follow_ups),
        tracing_reports=list(tracing_reports),
    )
    values = {
        key: value
        for key, value in MEDICATION_HISTORY_RECORD_MAPPING.row_values(record).items()
        if key != "event_id"
    }
    values.update(
        record_kind=record_kind,
        source_record_id=source_record_id,
        payload=payload,
        version=7,
        created_at=datetime(2026, 9, 10, tzinfo=UTC),
        updated_at=datetime(2026, 9, 15, tzinfo=UTC),
    )
    return values


def _expected_record_from_legacy_child(
    parent: MedicationHistoryRecord,
    child: FollowUpRecord,
) -> MedicationHistoryRecord:
    """移行前の子要素から、頭書き比較用のLEGACY_RECORD相当を作る。"""
    return replace(
        parent,
        id=MedicationHistoryRecordId(child.id.value),
        event_id=EventId.generate(),
        dispensing_id=None,
        prescription_id=None,
        counselor_id=child.counselor_id,
        counseled_at=child.followed_up_at,
        method=child.method,
        soap=child.soap,
        handbook_status=child.handbook_status,
        residual_drug=child.residual_drug,
        information_sheet_provided=child.information_sheet_provided,
        profile_updates=child.profile_updates,
        additional_notes=child.additional_notes,
        source_system=child.source_system,
        imported_at=None,
        recorded_by=child.recorded_by,
        recorded_at=(
            MedicationHistoryRecordedTimestamp(child.recorded_at.value)
            if child.recorded_at is not None
            else None
        ),
        status=MedicationHistoryStatus.LEGACY_RECORDED,
        amendments=(),
        tracing_reports=(),
        finalized_at=None,
        finalized_by=None,
        delay_reason=None,
        review_result=None,
    )


@pytest.mark.asyncio
async def test_tc45_49_52_64_migrationが独立薬歴と旧子要素をEvent鎖へ保全する(
    engine: AsyncEngine,
) -> None:
    """Event参照、旧監査日時、Reception、子FollowUpと報告書の帰属を保つ。"""
    corporate = create_corporate("薬歴Event移行検証")
    store = create_store(corporate_id=corporate.id)
    patient = create_patient(corporate_id=corporate.id)
    prescription = create_prescription(
        corporate_id=corporate.id,
        store_id=store.id,
        patient_id=patient.id,
    )
    dispensing = create_dispensing(
        corporate_id=corporate.id,
        store_id=store.id,
        patient_id=patient.id,
        prescription_id=prescription.id,
    )
    counselor_id = StaffId.generate()
    parent = create_record(
        corporate_id=corporate.id,
        store_id=store.id,
        patient_id=patient.id,
        dispensing_id=dispensing.id,
        prescription_id=prescription.id,
        counselor_id=counselor_id,
        profile_updates=ProfileUpdateIntents(
            new_allergies=(create_allergy_intent("そば"),)
        ),
    )
    parent_recorded_at = datetime(2026, 9, 11, 2, tzinfo=UTC)
    parent = replace(
        parent,
        recorded_by=counselor_id,
        recorded_at=MedicationHistoryRecordedTimestamp(parent_recorded_at),
    )
    parent = finalize_record_with_review(
        parent,
        finalized_by=counselor_id,
        finalized_at=FinalizedTimestamp(datetime(2026, 9, 12, 2, tzinfo=UTC)),
        delay_reason=FinalizationDelayReason("移行前の記録を検証するための遅延理由"),
    )
    child_id = FollowUpId.generate()
    child_recorded_at = datetime(2026, 9, 14, 2, tzinfo=UTC)
    child = create_follow_up(
        follow_up_id=child_id,
        counselor_id=counselor_id,
        followed_up_at=datetime(2026, 9, 13, 2, tzinfo=UTC),
        recorded_by=counselor_id,
        recorded_at=FollowUpRecordedTimestamp(child_recorded_at),
        profile_updates=ProfileUpdateIntents(
            new_allergies=(create_allergy_intent("卵"),)
        ),
    )
    child_payload = encode_aggregate(child)
    second_child_id = FollowUpId.generate()
    second_child = create_follow_up(
        follow_up_id=second_child_id,
        counselor_id=counselor_id,
        followed_up_at=datetime(2026, 9, 15, 2, tzinfo=UTC),
        recorded_by=counselor_id,
        recorded_at=FollowUpRecordedTimestamp(datetime(2026, 9, 16, 2, tzinfo=UTC)),
        profile_updates=ProfileUpdateIntents(
            new_allergies=(create_allergy_intent("えび"),)
        ),
    )
    second_child_payload = encode_aggregate(second_child)
    report_id = TracingReportId.generate()
    report_payload = encode_aggregate(
        create_tracing_report(
            report_id=report_id,
            reporter_id=counselor_id,
            response=create_tracing_report_response(
                received_by=counselor_id,
                content="次回処方時に調整します。",
            ),
        )
    )
    report_payload["follow_up_id"] = str(child_id.value)
    independent_follow_up = create_record(
        corporate_id=corporate.id,
        store_id=store.id,
        patient_id=patient.id,
        dispensing_id=dispensing.id,
        prescription_id=prescription.id,
        counselor_id=counselor_id,
    )
    independent_recorded_at = datetime(2026, 9, 16, 2, tzinfo=UTC)
    independent_follow_up = replace(
        independent_follow_up,
        recorded_by=counselor_id,
        recorded_at=MedicationHistoryRecordedTimestamp(independent_recorded_at),
    )
    independent_follow_up = finalize_record_with_review(
        independent_follow_up,
        finalized_by=counselor_id,
        finalized_at=FinalizedTimestamp(datetime(2026, 9, 17, 2, tzinfo=UTC)),
        delay_reason=FinalizationDelayReason("移行前の記録を検証するための遅延理由"),
    )
    expected_profile = PatientMedicalProfile.rebuild_from(
        corporate_id=corporate.id,
        patient_id=patient.id,
        records=(
            parent,
            independent_follow_up,
            _expected_record_from_legacy_child(parent, child),
            _expected_record_from_legacy_child(parent, second_child),
        ),
    )
    reception_id = ReceptionId.generate()
    reception_payload: dict[str, object] = {
        "id": str(reception_id.value),
        "corporate_id": str(corporate.id.value),
        "store_id": str(store.id.value),
        "patient_id": str(patient.id.value),
        "prescription_id": str(prescription.id.value),
        "dispensing_id": str(dispensing.id.value),
        "medication_history_id": str(parent.id.value),
    }

    async with engine.connect() as connection:
        transaction = await connection.begin()
        try:

            def migrate(sync_connection: Connection) -> None:
                target = _prepare_preceding_schema(sync_connection)
                aggregate_rows = (
                    (schema.corporates, _aggregate_row(CORPORATE_MAPPING, corporate)),
                    (schema.stores, _aggregate_row(STORE_MAPPING, store)),
                    (schema.patients, _aggregate_row(PATIENT_MAPPING, patient)),
                    (
                        schema.prescriptions,
                        _aggregate_row(PRESCRIPTION_MAPPING, prescription),
                    ),
                    (
                        schema.dispensing_processes,
                        _aggregate_row(DISPENSING_PROCESS_MAPPING, dispensing),
                    ),
                )
                for table, values in aggregate_rows:
                    sync_connection.execute(insert(table).values(**values))

                reception_table = schema.receptions
                sync_connection.execute(
                    insert(reception_table).values(
                        id=reception_id.value,
                        corporate_id=corporate.id.value,
                        store_id=store.id.value,
                        payload=reception_payload,
                        version=1,
                        created_at=_MIGRATED_AT,
                        updated_at=_MIGRATED_AT,
                    )
                )
                history_table = legacy_medication_history_table(
                    has_record_kind=True,
                    has_recorded_at=True,
                )
                sync_connection.execute(
                    insert(history_table).values(
                        **_legacy_record_values(
                            parent,
                            record_kind="initial",
                            source_record_id=None,
                            follow_ups=(child_payload, second_child_payload),
                            tracing_reports=(report_payload,),
                        )
                    )
                )
                sync_connection.execute(
                    insert(history_table).values(
                        **_legacy_record_values(
                            independent_follow_up,
                            record_kind="follow_up",
                            source_record_id=parent.id.value,
                        )
                    )
                )

                _run_migrations(
                    sync_connection,
                    operation="upgrade",
                    modules=[target],
                )

                counts_before_downgrade = tuple(
                    sync_connection.execute(
                        text(f"SELECT count(*) FROM {table_name}")
                    ).scalar_one()
                    for table_name in (
                        "care_events",
                        "event_definitions",
                        "medication_history_legacy_archives",
                    )
                )
                with (
                    Operations.context(
                        MigrationContext.configure(connection=sync_connection)
                    ),
                    pytest.raises(RuntimeError, match="Eventまたは移行記録"),
                ):
                    target.downgrade()
                counts_after_downgrade = tuple(
                    sync_connection.execute(
                        text(f"SELECT count(*) FROM {table_name}")
                    ).scalar_one()
                    for table_name in (
                        "care_events",
                        "event_definitions",
                        "medication_history_legacy_archives",
                    )
                )
                assert counts_after_downgrade == counts_before_downgrade

                parent_row, follow_up_row, child_row, second_child_row = (
                    sync_connection.execute(
                        text(
                            "SELECT id, event_id, status, counseled_at, recorded_at, "
                            "dispensing_id, prescription_id, payload, version "
                            "FROM medication_history_records WHERE id IN "
                            "(:parent_id, :follow_up_id, :child_id, :second_child_id) "
                            "ORDER BY id"
                        ),
                        {
                            "parent_id": parent.id.value,
                            "follow_up_id": independent_follow_up.id.value,
                            "child_id": child_id.value,
                            "second_child_id": second_child_id.value,
                        },
                    )
                    .mappings()
                    .all()
                )
                histories = {
                    row["id"]: row
                    for row in (
                        parent_row,
                        follow_up_row,
                        child_row,
                        second_child_row,
                    )
                }
                stored_parent = histories[parent.id.value]
                stored_follow_up = histories[independent_follow_up.id.value]
                stored_child = histories[child_id.value]
                stored_second_child = histories[second_child_id.value]
                migrated_records = tuple(
                    decode_aggregate(
                        cast(dict[str, object], row["payload"]),
                        MedicationHistoryRecord,
                    )
                    for row in histories.values()
                )
                migrated_profile = PatientMedicalProfile.rebuild_from(
                    corporate_id=corporate.id,
                    patient_id=patient.id,
                    records=migrated_records,
                )
                assert migrated_profile.allergies == expected_profile.allergies
                assert migrated_profile.source_record_ids == (
                    expected_profile.source_record_ids
                )
                parent_event_id = stored_parent["event_id"]
                follow_up_event_id = stored_follow_up["event_id"]
                child_event_id = stored_child["event_id"]

                assert stored_parent["status"] == "finalized"
                assert stored_parent["recorded_at"] == parent_recorded_at
                assert stored_parent["version"] == 7
                assert stored_parent["prescription_id"] == prescription.id.value
                assert stored_parent["dispensing_id"] == dispensing.id.value
                assert "record_kind" not in stored_parent["payload"]
                assert "source_record_id" not in stored_parent["payload"]
                assert "follow_ups" not in stored_parent["payload"]
                assert stored_parent["payload"]["event_id"] == str(parent_event_id)
                assert stored_parent["payload"]["finalized_at"] == (
                    "2026-09-12T02:00:00+00:00"
                )

                assert stored_follow_up["status"] == "finalized"
                assert stored_follow_up["recorded_at"] == independent_recorded_at
                assert stored_follow_up["version"] == 7
                assert stored_follow_up["prescription_id"] is None
                assert stored_follow_up["dispensing_id"] is None

                assert stored_child["status"] == "legacy_recorded"
                assert stored_child["counseled_at"] == datetime(
                    2026, 9, 13, 2, tzinfo=UTC
                )
                assert stored_child["recorded_at"] == child_recorded_at
                assert stored_child["payload"]["counselor_id"] == str(
                    counselor_id.value
                )
                assert stored_child["payload"]["recorded_by"] == str(counselor_id.value)
                assert stored_child["payload"]["status"] == "legacy_recorded"
                assert stored_second_child["status"] == "legacy_recorded"
                assert stored_second_child["counseled_at"] == datetime(
                    2026, 9, 15, 2, tzinfo=UTC
                )

                event_rows = sync_connection.execute(
                    text(
                        "SELECT id, event_type_standard_code, occurred_at, "
                        "occurred_at_is_unknown, created_at, related_event_id, reception_id, "
                        "prescription_id, dispensing_id FROM care_events WHERE id IN "
                        "(:parent_event_id, :follow_up_event_id, :child_event_id, "
                        ":second_child_event_id)"
                    ),
                    {
                        "parent_event_id": parent_event_id,
                        "follow_up_event_id": follow_up_event_id,
                        "child_event_id": child_event_id,
                        "second_child_event_id": stored_second_child["event_id"],
                    },
                ).mappings()
                events = {row["id"]: row for row in event_rows}
                initial_event = events[parent_event_id]
                assert (
                    initial_event["event_type_standard_code"]
                    == "prescription_reception"
                )
                assert initial_event["occurred_at"] is None
                assert initial_event["occurred_at_is_unknown"] is True
                assert initial_event["reception_id"] == reception_id.value
                assert initial_event["prescription_id"] == prescription.id.value
                assert initial_event["dispensing_id"] == dispensing.id.value
                assert events[follow_up_event_id]["event_type_standard_code"] == (
                    "medication_period_follow_up"
                )
                assert events[follow_up_event_id]["related_event_id"] == parent_event_id
                assert events[follow_up_event_id]["occurred_at"] == datetime(
                    2026, 8, 24, 5, tzinfo=UTC
                )
                assert events[child_event_id]["related_event_id"] == parent_event_id
                assert events[child_event_id]["occurred_at"] == datetime(
                    2026, 9, 13, 2, tzinfo=UTC
                )
                assert events[stored_second_child["event_id"]]["related_event_id"] == (
                    parent_event_id
                )
                assert events[stored_second_child["event_id"]]["occurred_at"] == (
                    datetime(2026, 9, 15, 2, tzinfo=UTC)
                )
                created_at_values = {row["created_at"] for row in events.values()}
                assert len(created_at_values) == 1
                assert next(iter(created_at_values)) != _MIGRATED_AT

                migrated_reception = (
                    sync_connection.execute(
                        text("SELECT event_id, payload FROM receptions WHERE id = :id"),
                        {"id": reception_id.value},
                    )
                    .mappings()
                    .one()
                )
                assert migrated_reception["event_id"] == parent_event_id
                assert migrated_reception["payload"]["event_id"] == str(parent_event_id)

                archive_rows = sync_connection.execute(
                    text(
                        "SELECT legacy_record_id, legacy_parent_record_id, archive_kind, "
                        "original_payload, archived_at FROM "
                        "medication_history_legacy_archives"
                    )
                ).mappings()
                archives = {row["legacy_record_id"]: row for row in archive_rows}
                assert set(archives) == {
                    parent.id.value,
                    independent_follow_up.id.value,
                    child_id.value,
                    second_child_id.value,
                }
                assert (
                    archives[child_id.value]["legacy_parent_record_id"]
                    == parent.id.value
                )
                assert archives[child_id.value]["archive_kind"] == "follow_up"
                assert archives[child_id.value]["original_payload"] == child_payload
                assert archives[parent.id.value]["original_payload"]["follow_ups"] == [
                    child_payload,
                    second_child_payload,
                ]
                assert {
                    archive["archived_at"] for archive in archives.values()
                } == created_at_values
                child_report = stored_child["payload"]["tracing_reports"][0]
                assert child_report["id"] == str(report_id.value)
                assert "follow_up_id" not in child_report
                assert child_report["response"]["content"] == "次回処方時に調整します。"
                report_link = sync_connection.execute(
                    text(
                        "SELECT target_record_id FROM legacy_tracing_report_links "
                        "WHERE legacy_parent_record_id = :parent_id "
                        "AND legacy_tracing_report_id = :report_id"
                    ),
                    {"parent_id": parent.id.value, "report_id": report_id.value},
                ).scalar_one()
                assert report_link == child_id.value

            await connection.run_sync(migrate)
        finally:
            await transaction.rollback()


@pytest.mark.parametrize(
    ("invalid_case", "expected_message"),
    (
        ("孤立した参照元", "参照元が見つかりません"),
        ("患者が異なる参照元", "参照先スコープが異なります"),
        ("重複した子ID", "が重複しています"),
        ("曖昧なReception", "複数のReception"),
        ("未対応の子payload", "follow_upsが配列ではありません"),
    ),
)
@pytest.mark.asyncio
async def test_tc45_55_壊れた旧データは変更前にmigrationを拒否する(
    engine: AsyncEngine,
    invalid_case: str,
    expected_message: str,
) -> None:
    """事前検査で拒否し、DDL・薬歴・Eventを部分的に残さない。"""
    corporate = create_corporate(f"{invalid_case}移行検証")
    store = create_store(corporate_id=corporate.id)
    patient = create_patient(corporate_id=corporate.id)
    prescription = create_prescription(
        corporate_id=corporate.id,
        store_id=store.id,
        patient_id=patient.id,
    )
    dispensing = create_dispensing(
        corporate_id=corporate.id,
        store_id=store.id,
        patient_id=patient.id,
        prescription_id=prescription.id,
    )
    counselor_id = StaffId.generate()
    primary = create_record(
        corporate_id=corporate.id,
        store_id=store.id,
        patient_id=patient.id,
        prescription_id=prescription.id,
        dispensing_id=dispensing.id,
        counselor_id=counselor_id,
    )
    records: list[tuple[MedicationHistoryRecord, str, UUID | None]] = [
        (primary, "initial", None)
    ]
    aggregate_rows: list[tuple[Any, dict[str, object]]] = [
        (schema.corporates, _aggregate_row(CORPORATE_MAPPING, corporate)),
        (schema.stores, _aggregate_row(STORE_MAPPING, store)),
        (schema.patients, _aggregate_row(PATIENT_MAPPING, patient)),
        (
            schema.prescriptions,
            _aggregate_row(PRESCRIPTION_MAPPING, prescription),
        ),
        (
            schema.dispensing_processes,
            _aggregate_row(DISPENSING_PROCESS_MAPPING, dispensing),
        ),
    ]

    second_patient = None
    second_prescription = None
    second_dispensing = None
    if invalid_case == "患者が異なる参照元":
        second_patient = create_patient(corporate_id=corporate.id, patient_number=2)
        second_prescription = create_prescription(
            corporate_id=corporate.id,
            store_id=store.id,
            patient_id=second_patient.id,
        )
        second_dispensing = create_dispensing(
            corporate_id=corporate.id,
            store_id=store.id,
            patient_id=second_patient.id,
            prescription_id=second_prescription.id,
        )
        second = create_record(
            corporate_id=corporate.id,
            store_id=store.id,
            patient_id=second_patient.id,
            prescription_id=second_prescription.id,
            dispensing_id=second_dispensing.id,
            counselor_id=counselor_id,
        )
        records.append((second, "follow_up", primary.id.value))
        aggregate_rows.extend(
            [
                (schema.patients, _aggregate_row(PATIENT_MAPPING, second_patient)),
                (
                    schema.prescriptions,
                    _aggregate_row(PRESCRIPTION_MAPPING, second_prescription),
                ),
                (
                    schema.dispensing_processes,
                    _aggregate_row(DISPENSING_PROCESS_MAPPING, second_dispensing),
                ),
            ]
        )
    elif invalid_case == "孤立した参照元":
        records[0] = (primary, "follow_up", UUID(int=1))

    async with engine.connect() as connection:
        transaction = await connection.begin()
        try:

            def migrate(sync_connection: Connection) -> None:
                target = _prepare_preceding_schema(sync_connection)
                for table, values in aggregate_rows:
                    sync_connection.execute(insert(table).values(**values))

                history_table = legacy_medication_history_table(
                    has_record_kind=True,
                    has_recorded_at=True,
                )
                if invalid_case in ("孤立した参照元", "患者が異なる参照元"):
                    sync_connection.execute(
                        text(
                            "ALTER TABLE medication_history_records DROP CONSTRAINT "
                            "fk_medication_history_records_source_identity"
                        )
                    )
                history_values = [
                    _legacy_record_values(
                        record,
                        record_kind=record_kind,
                        source_record_id=source_id,
                        follow_ups=(
                            (
                                encode_aggregate(
                                    create_follow_up(
                                        counselor_id=counselor_id,
                                        followed_up_at=datetime(
                                            2026, 9, 18, tzinfo=UTC
                                        ),
                                    )
                                ),
                            )
                            * 2
                            if invalid_case == "重複した子ID"
                            else ()
                        ),
                    )
                    for record, record_kind, source_id in records
                ]
                if invalid_case == "未対応の子payload":
                    original_payload = history_values[0]["payload"]
                    assert isinstance(original_payload, dict)
                    payload = dict(original_payload)
                    payload["follow_ups"] = "未対応形式"
                    history_values[0]["payload"] = payload
                sync_connection.execute(insert(history_table), history_values)

                if invalid_case in ("孤立した参照元", "患者が異なる参照元"):
                    sync_connection.execute(
                        text(
                            "ALTER TABLE medication_history_records ADD CONSTRAINT "
                            "fk_medication_history_records_source_identity "
                            "FOREIGN KEY (source_record_id, corporate_id, patient_id, "
                            "prescription_id, dispensing_id) REFERENCES "
                            "medication_history_records (id, corporate_id, patient_id, "
                            "prescription_id, dispensing_id) NOT VALID"
                        )
                    )

                if invalid_case == "曖昧なReception":
                    for _ in range(2):
                        reception_id = ReceptionId.generate()
                        sync_connection.execute(
                            insert(schema.receptions).values(
                                id=reception_id.value,
                                corporate_id=corporate.id.value,
                                store_id=store.id.value,
                                payload={
                                    "id": str(reception_id.value),
                                    "corporate_id": str(corporate.id.value),
                                    "store_id": str(store.id.value),
                                    "patient_id": str(patient.id.value),
                                    "prescription_id": str(prescription.id.value),
                                    "dispensing_id": str(dispensing.id.value),
                                    "medication_history_id": str(primary.id.value),
                                },
                                version=1,
                                created_at=_MIGRATED_AT,
                                updated_at=_MIGRATED_AT,
                            )
                        )

                savepoint = sync_connection.begin_nested()
                try:
                    _run_migrations(
                        sync_connection,
                        operation="upgrade",
                        modules=[target],
                    )
                except RuntimeError as error:
                    assert expected_message in str(error)
                    savepoint.rollback()
                else:
                    savepoint.rollback()
                    pytest.fail("不正な旧データのmigrationが成功した。")

                assert (
                    sync_connection.execute(
                        text("SELECT to_regclass('public.care_events')")
                    ).scalar_one()
                    is None
                )
                assert (
                    sync_connection.execute(
                        text(
                            "SELECT count(*) FROM medication_history_records WHERE id = :id"
                        ),
                        {"id": primary.id.value},
                    ).scalar_one()
                    == 1
                )
                assert (
                    sync_connection.execute(
                        text(
                            "SELECT count(*) FROM information_schema.columns WHERE "
                            "table_name = 'medication_history_records' AND column_name = "
                            "'event_id'"
                        )
                    ).scalar_one()
                    == 0
                )

                if invalid_case == "未対応の子payload":
                    original_payload = history_values[0]["payload"]
                    assert isinstance(original_payload, dict)
                    corrected_payload = dict(original_payload)
                    corrected_payload["follow_ups"] = []
                    sync_connection.execute(
                        history_table.update()
                        .where(history_table.c.id == primary.id.value)
                        .values(payload=corrected_payload)
                    )
                    _run_migrations(
                        sync_connection,
                        operation="upgrade",
                        modules=[target],
                    )
                    assert (
                        sync_connection.execute(
                            text("SELECT count(*) FROM care_events")
                        ).scalar_one()
                        == 1
                    )
                    assert (
                        sync_connection.execute(
                            text("SELECT count(*) FROM event_definitions")
                        ).scalar_one()
                        == 6
                    )
                    migrated_row = (
                        sync_connection.execute(
                            text(
                                "SELECT version, recorded_at, payload FROM "
                                "medication_history_records WHERE id = :id"
                            ),
                            {"id": primary.id.value},
                        )
                        .mappings()
                        .one()
                    )
                    assert migrated_row["version"] == 7
                    assert "follow_ups" not in migrated_row["payload"]
                    assert migrated_row["payload"]["event_id"]
                    archived_payload = sync_connection.execute(
                        text(
                            "SELECT original_payload FROM "
                            "medication_history_legacy_archives WHERE legacy_record_id = :id"
                        ),
                        {"id": primary.id.value},
                    ).scalar_one()
                    assert archived_payload["follow_ups"] == []

            await connection.run_sync(migrate)
        finally:
            await transaction.rollback()


@pytest.mark.asyncio
async def test_tc45_57_新行のないDBではmigrationを安全にdowngradeできる(
    engine: AsyncEngine,
) -> None:
    """空の新schemaから旧schemaへ戻して新しい列と表を除去する。"""
    async with engine.connect() as connection:
        transaction = await connection.begin()
        try:

            def migrate(sync_connection: Connection) -> None:
                target = _prepare_preceding_schema(sync_connection)
                _run_migrations(
                    sync_connection,
                    operation="upgrade",
                    modules=[target],
                )
                _run_migrations(
                    sync_connection,
                    operation="downgrade",
                    modules=[target],
                )
                assert (
                    sync_connection.execute(
                        text("SELECT to_regclass('public.care_events')")
                    ).scalar_one()
                    is None
                )
                assert (
                    sync_connection.execute(
                        text(
                            "SELECT count(*) FROM information_schema.columns WHERE "
                            "table_name = 'medication_history_records' AND column_name = "
                            "'event_id'"
                        )
                    ).scalar_one()
                    == 0
                )

            await connection.run_sync(migrate)
        finally:
            await transaction.rollback()


def test_tc45_57_オフラインdowngradeも削除より先に保護条件を生成する() -> None:
    """生成SQLにEvent・カスタム定義・旧子記録のguardが含まれる。"""
    target = next(
        module
        for module in ordered_migrations()
        if str(module.revision) == _TARGET_REVISION
    )
    output = StringIO()
    context = MigrationContext.configure(
        url="postgresql://",
        opts={"as_sql": True, "output_buffer": output},
    )

    with Operations.context(context):
        target.downgrade()

    generated = output.getvalue()
    guard = generated.index("DO $$ BEGIN")
    first_drop = generated.index("DROP TRIGGER")
    assert "EXISTS (SELECT 1 FROM care_events)" in generated
    assert (
        "EXISTS (SELECT 1 FROM event_definitions WHERE corporate_id IS NOT NULL)"
        in generated
    )
    assert "archive_kind = 'follow_up'" in generated
    assert guard < first_drop
