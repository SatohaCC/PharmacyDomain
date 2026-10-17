"""業務EventとEvent起点薬歴へ移行し、旧フォローアップを保全する。"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import cast

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260927_0010"
down_revision: str | None = "20260926_0009"
branch_labels: str | None = None
depends_on: str | None = None

_STANDARD_DEFINITIONS = (
    ("prescription_reception", "処方箋受付"),
    ("medication_period_follow_up", "服薬期間中フォローアップ"),
    ("telephone_follow_up", "電話フォローアップ"),
    ("in_person_consultation", "来局相談"),
    ("home_visit", "在宅訪問"),
    ("online_medication_guidance", "オンライン服薬指導"),
)
_DEFINITION_IDS = {code: uuid.uuid7() for code, _name in _STANDARD_DEFINITIONS}
_PRESCRIPTION_EVENT = "prescription_reception"
_FOLLOW_UP_EVENT = "medication_period_follow_up"


def upgrade() -> None:
    """Event定義・履歴を作り、既存薬歴と入れ子フォローアップを変換する。"""
    op.create_table(
        "event_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("corporate_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("standard_code", sa.String(length=80), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(corporate_id IS NULL AND standard_code IS NOT NULL) OR "
            "(corporate_id IS NOT NULL AND standard_code IS NULL)",
            name="ck_event_definitions_standard_or_corporate",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_event_definitions"),
        sa.UniqueConstraint(
            "id", "corporate_id", name="uq_event_definitions_identity_scope"
        ),
    )
    op.create_index(
        "uq_event_definitions_standard_code",
        "event_definitions",
        ["standard_code"],
        unique=True,
        postgresql_where=sa.text("corporate_id IS NULL"),
    )
    op.create_index(
        "uq_event_definitions_corporate_active_name",
        "event_definitions",
        ["corporate_id", "name"],
        unique=True,
        postgresql_where=sa.text("corporate_id IS NOT NULL AND is_active"),
    )
    op.create_unique_constraint(
        "uq_prescriptions_scope_identity",
        "prescriptions",
        ["id", "corporate_id", "store_id", "patient_id"],
    )
    op.create_unique_constraint(
        "uq_dispensing_processes_event_identity",
        "dispensing_processes",
        ["id", "corporate_id", "store_id", "patient_id", "prescription_id"],
    )
    op.create_table(
        "care_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_definition_corporate_id", postgresql.UUID(as_uuid=True)),
        sa.Column("event_type_standard_code", sa.String(length=80)),
        sa.Column("event_type_name", sa.String(length=200), nullable=False),
        sa.Column("corporate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True)),
        sa.Column("occurred_at_is_unknown", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("related_event_id", postgresql.UUID(as_uuid=True)),
        sa.Column("reception_id", postgresql.UUID(as_uuid=True)),
        sa.Column("prescription_id", postgresql.UUID(as_uuid=True)),
        sa.Column("dispensing_id", postgresql.UUID(as_uuid=True)),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(occurred_at IS NOT NULL AND NOT occurred_at_is_unknown) OR "
            "(occurred_at IS NULL AND occurred_at_is_unknown)",
            name="ck_care_events_occurred_at_known_state",
        ),
        sa.CheckConstraint(
            "event_definition_corporate_id IS NULL OR "
            "event_definition_corporate_id = corporate_id",
            name="ck_care_events_event_type_corporate_scope",
        ),
        sa.CheckConstraint(
            "related_event_id IS NULL OR related_event_id <> id",
            name="ck_care_events_not_self_related",
        ),
        sa.CheckConstraint(
            "dispensing_id IS NULL OR prescription_id IS NOT NULL",
            name="ck_care_events_dispensing_requires_prescription",
        ),
        sa.ForeignKeyConstraint(
            ["event_type_id"],
            ["event_definitions.id"],
            name="fk_care_events_event_type",
        ),
        sa.ForeignKeyConstraint(
            ["event_type_id", "event_definition_corporate_id"],
            ["event_definitions.id", "event_definitions.corporate_id"],
            name="fk_care_events_event_type_scope",
        ),
        sa.ForeignKeyConstraint(
            ["related_event_id", "corporate_id", "patient_id"],
            ["care_events.id", "care_events.corporate_id", "care_events.patient_id"],
            name="fk_care_events_related_scope",
        ),
        sa.ForeignKeyConstraint(
            ["corporate_id", "store_id", "reception_id"],
            ["receptions.corporate_id", "receptions.store_id", "receptions.id"],
            name="fk_care_events_reception_scope",
        ),
        sa.ForeignKeyConstraint(
            ["prescription_id", "corporate_id", "store_id", "patient_id"],
            [
                "prescriptions.id",
                "prescriptions.corporate_id",
                "prescriptions.store_id",
                "prescriptions.patient_id",
            ],
            name="fk_care_events_prescription_scope",
        ),
        sa.ForeignKeyConstraint(
            [
                "dispensing_id",
                "corporate_id",
                "store_id",
                "patient_id",
                "prescription_id",
            ],
            [
                "dispensing_processes.id",
                "dispensing_processes.corporate_id",
                "dispensing_processes.store_id",
                "dispensing_processes.patient_id",
                "dispensing_processes.prescription_id",
            ],
            name="fk_care_events_dispensing_scope",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_care_events"),
        sa.UniqueConstraint(
            "id", "corporate_id", "patient_id", name="uq_care_events_scope_identity"
        ),
        sa.UniqueConstraint(
            "id",
            "corporate_id",
            "store_id",
            "patient_id",
            name="uq_care_events_full_scope_identity",
        ),
        sa.UniqueConstraint(
            "id",
            "corporate_id",
            "store_id",
            "patient_id",
            "prescription_id",
            "dispensing_id",
            name="uq_care_events_resource_identity",
        ),
        sa.UniqueConstraint(
            "id",
            "corporate_id",
            "store_id",
            "reception_id",
            name="uq_care_events_reception_identity",
        ),
    )
    op.create_index(
        "ix_care_events_corporate_store_patient_occurred_at",
        "care_events",
        ["corporate_id", "store_id", "patient_id", "occurred_at", "id"],
    )
    op.create_index(
        "uq_care_events_reception",
        "care_events",
        ["corporate_id", "store_id", "reception_id"],
        unique=True,
        postgresql_where=sa.text("reception_id IS NOT NULL"),
    )

    op.add_column(
        "medication_history_records",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.alter_column(
        "medication_history_records",
        "dispensing_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )
    op.alter_column(
        "medication_history_records",
        "prescription_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )
    op.add_column("receptions", sa.Column("event_id", postgresql.UUID(as_uuid=True)))

    op.create_table(
        "medication_history_legacy_archives",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("legacy_record_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("legacy_parent_record_id", postgresql.UUID(as_uuid=True)),
        sa.Column("corporate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("archive_kind", sa.String(length=32), nullable=False),
        sa.Column(
            "original_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(archive_kind = 'record' AND legacy_parent_record_id IS NULL) OR "
            "(archive_kind = 'follow_up' AND legacy_parent_record_id IS NOT NULL)",
            name="ck_medication_history_legacy_archives_archive_kind_parent",
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["care_events.id"],
            name="fk_medication_history_legacy_archives_event",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_medication_history_legacy_archives"),
        sa.UniqueConstraint(
            "legacy_record_id", name="uq_medication_history_legacy_archives_record"
        ),
    )
    op.create_table(
        "legacy_tracing_report_links",
        sa.Column("corporate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "legacy_parent_record_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column(
            "legacy_tracing_report_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("target_record_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["legacy_parent_record_id"],
            ["medication_history_records.id"],
            name="fk_legacy_tracing_report_links_parent",
        ),
        sa.ForeignKeyConstraint(
            ["target_record_id"],
            ["medication_history_records.id"],
            name="fk_legacy_tracing_report_links_target",
        ),
        sa.PrimaryKeyConstraint(
            "corporate_id",
            "legacy_parent_record_id",
            "legacy_tracing_report_id",
            name="pk_legacy_tracing_report_links",
        ),
    )

    applied_at = datetime.now(UTC)
    event_type_ids = _seed_standard_definitions(applied_at)
    _backfill_records(applied_at, event_type_ids)

    op.alter_column(
        "medication_history_records",
        "event_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    op.drop_index(
        "uq_medication_history_records_finalized_dispensing",
        table_name="medication_history_records",
    )
    op.drop_constraint(
        "ck_medication_history_records_record_kind_source",
        "medication_history_records",
        type_="check",
    )
    op.drop_constraint(
        "fk_medication_history_records_source_identity",
        "medication_history_records",
        type_="foreignkey",
    )
    op.drop_constraint(
        "uq_medication_history_records_source_identity",
        "medication_history_records",
        type_="unique",
    )
    op.drop_column("medication_history_records", "source_record_id")
    op.drop_column("medication_history_records", "record_kind")
    op.create_foreign_key(
        "fk_receptions_event_scope",
        "receptions",
        "care_events",
        ["event_id", "corporate_id", "store_id", "id"],
        ["id", "corporate_id", "store_id", "reception_id"],
    )
    op.create_unique_constraint("uq_receptions_event", "receptions", ["event_id"])
    op.create_foreign_key(
        "fk_medication_history_records_event_scope",
        "medication_history_records",
        "care_events",
        ["event_id", "corporate_id", "store_id", "patient_id"],
        ["id", "corporate_id", "store_id", "patient_id"],
    )
    op.create_unique_constraint(
        "uq_medication_history_records_event",
        "medication_history_records",
        ["event_id"],
    )
    op.create_foreign_key(
        "fk_medication_history_records_event_resources",
        "medication_history_records",
        "care_events",
        [
            "event_id",
            "corporate_id",
            "store_id",
            "patient_id",
            "prescription_id",
            "dispensing_id",
        ],
        [
            "id",
            "corporate_id",
            "store_id",
            "patient_id",
            "prescription_id",
            "dispensing_id",
        ],
    )
    op.create_foreign_key(
        "fk_medication_history_records_dispensing_scope",
        "medication_history_records",
        "dispensing_processes",
        ["dispensing_id", "corporate_id", "store_id", "patient_id", "prescription_id"],
        ["id", "corporate_id", "store_id", "patient_id", "prescription_id"],
    )
    op.create_check_constraint(
        "ck_medication_history_records_dispensing_requires_prescription",
        "medication_history_records",
        "dispensing_id IS NULL OR prescription_id IS NOT NULL",
    )
    op.create_index(
        "uq_medication_history_records_finalized_dispensing",
        "medication_history_records",
        ["corporate_id", "dispensing_id"],
        unique=True,
        postgresql_where=sa.text("status = 'finalized' AND dispensing_id IS NOT NULL"),
    )

    _create_routines()


def downgrade() -> None:
    """Event・カスタム定義・旧子記録が残る場合は削除前に拒否する。"""
    guard = (
        "DO $$ BEGIN "
        "IF EXISTS (SELECT 1 FROM care_events) OR "
        "EXISTS (SELECT 1 FROM event_definitions WHERE corporate_id IS NOT NULL) OR "
        "EXISTS (SELECT 1 FROM medication_history_legacy_archives WHERE archive_kind = 'follow_up') "
        "THEN RAISE EXCEPTION 'Eventまたは移行記録が残っているため旧スキーマへ戻せません。'; "
        "END IF; END $$"
    )
    if op.get_context().as_sql:
        op.execute(guard)
    else:
        has_new_data = (
            op.get_bind()
            .execute(
                sa.text(
                    "SELECT EXISTS (SELECT 1 FROM care_events) OR "
                    "EXISTS (SELECT 1 FROM event_definitions WHERE corporate_id IS NOT NULL) OR "
                    "EXISTS (SELECT 1 FROM medication_history_legacy_archives "
                    "WHERE archive_kind = 'follow_up')"
                )
            )
            .scalar_one()
        )
        if has_new_data:
            raise RuntimeError(
                "Eventまたは移行記録が残っているため旧スキーマへ戻せません。"
            )

    _drop_routines()
    op.drop_index(
        "uq_medication_history_records_finalized_dispensing",
        table_name="medication_history_records",
    )
    op.drop_constraint(
        "ck_medication_history_records_dispensing_requires_prescription",
        "medication_history_records",
        type_="check",
    )
    op.drop_constraint(
        "fk_medication_history_records_dispensing_scope",
        "medication_history_records",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_medication_history_records_event_resources",
        "medication_history_records",
        type_="foreignkey",
    )
    op.drop_constraint(
        "uq_medication_history_records_event",
        "medication_history_records",
        type_="unique",
    )
    op.drop_constraint(
        "fk_medication_history_records_event_scope",
        "medication_history_records",
        type_="foreignkey",
    )
    op.drop_constraint("uq_receptions_event", "receptions", type_="unique")
    op.drop_constraint("fk_receptions_event_scope", "receptions", type_="foreignkey")
    op.create_index(
        "uq_medication_history_records_finalized_dispensing",
        "medication_history_records",
        ["corporate_id", "dispensing_id"],
        unique=True,
        postgresql_where=sa.text("status = 'finalized'"),
    )
    op.drop_column("receptions", "event_id")
    op.drop_column("medication_history_records", "event_id")
    op.alter_column(
        "medication_history_records",
        "prescription_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    op.alter_column(
        "medication_history_records",
        "dispensing_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    op.drop_table("legacy_tracing_report_links")
    op.drop_table("medication_history_legacy_archives")
    op.drop_index("uq_care_events_reception", table_name="care_events")
    op.drop_index(
        "ix_care_events_corporate_store_patient_occurred_at",
        table_name="care_events",
    )
    op.drop_table("care_events")
    op.drop_constraint(
        "uq_dispensing_processes_event_identity",
        "dispensing_processes",
        type_="unique",
    )
    op.drop_constraint(
        "uq_prescriptions_scope_identity", "prescriptions", type_="unique"
    )
    op.drop_index(
        "uq_event_definitions_corporate_active_name", table_name="event_definitions"
    )
    op.drop_index("uq_event_definitions_standard_code", table_name="event_definitions")
    op.drop_table("event_definitions")


def _seed_standard_definitions(created_at: datetime) -> dict[str, uuid.UUID]:
    """標準種別をUUIDv7で登録し、Event変換用IDを返す。"""
    table = sa.table(
        "event_definitions",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("corporate_id", postgresql.UUID(as_uuid=True)),
        sa.column("standard_code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("is_active", sa.Boolean()),
        sa.column("payload", postgresql.JSONB()),
        sa.column("version", sa.Integer()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    rows: list[dict[str, object]] = []
    for code, name in _STANDARD_DEFINITIONS:
        definition_id = _DEFINITION_IDS[code]
        rows.append(
            {
                "id": definition_id,
                "corporate_id": None,
                "standard_code": code,
                "name": name,
                "is_active": True,
                "payload": {
                    "id": str(definition_id),
                    "name": name,
                    "corporate_id": None,
                    "standard_code": code,
                    "is_active": True,
                },
                "version": 1,
                "created_at": created_at,
                "updated_at": created_at,
            }
        )
    op.get_bind().execute(table.insert(), rows)
    return dict(_DEFINITION_IDS)


def _backfill_records(
    migrated_at: datetime, event_type_ids: Mapping[str, uuid.UUID]
) -> None:
    """旧薬歴、Receptionとの関連、入れ子フォローアップを変換する。"""
    bind = op.get_bind()
    rows = (
        bind.execute(
            sa.text(
                "SELECT id, corporate_id, store_id, patient_id, dispensing_id, "
                "prescription_id, status, counseled_at, recorded_at, record_kind, "
                "source_record_id, payload FROM medication_history_records ORDER BY id FOR UPDATE"
            )
        )
        .mappings()
        .all()
    )
    records: dict[uuid.UUID, dict[str, object]] = {}
    children: dict[
        uuid.UUID, tuple[uuid.UUID, dict[str, object], dict[str, object]]
    ] = {}
    event_ids: dict[uuid.UUID, uuid.UUID] = {}
    child_event_ids: dict[uuid.UUID, uuid.UUID] = {}

    for raw_row in rows:
        row = dict(cast(Mapping[str, object], raw_row))
        record_id = _uuid(row["id"], "薬歴ID")
        payload = _mapping(row["payload"], "薬歴payload")
        _validate_parent_row(row, payload)
        if record_id in records:
            raise RuntimeError("薬歴IDが重複しているため移行できません。")
        records[record_id] = row
        event_ids[record_id] = uuid.uuid7()
        nested = payload.get("follow_ups", [])
        if not isinstance(nested, list):
            raise RuntimeError(f"薬歴 {record_id} のfollow_upsが配列ではありません。")
        seen_child_ids: set[uuid.UUID] = set()
        for item in nested:
            child = _mapping(item, f"薬歴 {record_id} のfollow_up")
            child_id = _uuid(child.get("id"), "旧フォローアップID")
            if (
                child_id in seen_child_ids
                or child_id in event_ids
                or child_id in children
            ):
                raise RuntimeError(f"旧フォローアップID {child_id} が重複しています。")
            seen_child_ids.add(child_id)
            child_event_ids[child_id] = uuid.uuid7()
            children[child_id] = (record_id, child, {})

    all_record_ids = set(records) | set(children)
    if len(all_record_ids) != len(records) + len(children):
        raise RuntimeError("旧フォローアップIDが薬歴IDと重複しています。")

    _validate_source_links(records)
    report_groups = _group_legacy_reports(records, children)
    receptions = _load_reception_links(records)
    reception_for_record = _validate_reception_links(records, receptions)

    event_rows = _build_parent_events(
        records,
        event_ids,
        event_type_ids,
        migrated_at,
        reception_for_record,
    )
    child_rows = _build_child_events(
        children,
        event_ids,
        child_event_ids,
        event_type_ids,
        migrated_at,
    )
    insert_event_rows = _topological_events(event_rows, child_rows, records)
    event_table = sa.table(
        "care_events",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("event_type_id", postgresql.UUID(as_uuid=True)),
        sa.column("event_definition_corporate_id", postgresql.UUID(as_uuid=True)),
        sa.column("event_type_standard_code", sa.String()),
        sa.column("event_type_name", sa.String()),
        sa.column("corporate_id", postgresql.UUID(as_uuid=True)),
        sa.column("store_id", postgresql.UUID(as_uuid=True)),
        sa.column("patient_id", postgresql.UUID(as_uuid=True)),
        sa.column("occurred_at", sa.DateTime(timezone=True)),
        sa.column("occurred_at_is_unknown", sa.Boolean()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("related_event_id", postgresql.UUID(as_uuid=True)),
        sa.column("reception_id", postgresql.UUID(as_uuid=True)),
        sa.column("prescription_id", postgresql.UUID(as_uuid=True)),
        sa.column("dispensing_id", postgresql.UUID(as_uuid=True)),
        sa.column("payload", postgresql.JSONB()),
        sa.column("version", sa.Integer()),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    for event in insert_event_rows:
        bind.execute(event_table.insert().values(**event))

    _archive_and_update_histories(
        records,
        children,
        event_ids,
        child_event_ids,
        migrated_at,
        report_groups,
        receptions,
        reception_for_record,
    )


def _validate_parent_row(
    row: Mapping[str, object], payload: Mapping[str, object]
) -> None:
    """移行前のpayloadと検索列が既に食い違っていないことを確認する。"""
    for key in (
        "id",
        "corporate_id",
        "store_id",
        "patient_id",
        "dispensing_id",
        "prescription_id",
    ):
        if str(payload.get(key)) != str(row.get(key)):
            raise RuntimeError(f"薬歴 {row.get('id')} の{key}がpayloadと一致しません。")
    if payload.get("record_kind") != row.get("record_kind"):
        raise RuntimeError(f"薬歴 {row.get('id')} の種別がpayloadと一致しません。")
    if str(payload.get("source_record_id")) != str(row.get("source_record_id")):
        raise RuntimeError(f"薬歴 {row.get('id')} の参照元がpayloadと一致しません。")
    if payload.get("status") != row.get("status"):
        raise RuntimeError(f"薬歴 {row.get('id')} の状態がpayloadと一致しません。")
    if row.get("record_kind") not in {"initial", "follow_up"}:
        raise RuntimeError(f"薬歴 {row.get('id')} の種別が想定外です。")


def _validate_source_links(records: Mapping[uuid.UUID, Mapping[str, object]]) -> None:
    """旧独立フォローアップの参照先と循環の有無を検証する。"""
    sources: dict[uuid.UUID, uuid.UUID] = {}
    for record_id, row in records.items():
        kind = row.get("record_kind")
        source = row.get("source_record_id")
        if kind == "initial":
            if source is not None:
                raise RuntimeError(f"初回薬歴 {record_id} に参照元があります。")
            continue
        if source is None:
            raise RuntimeError(f"フォローアップ薬歴 {record_id} の参照元がありません。")
        source_id = _uuid(source, "参照元薬歴ID")
        parent = records.get(source_id)
        if parent is None:
            raise RuntimeError(
                f"フォローアップ薬歴 {record_id} の参照元が見つかりません。"
            )
        if any(
            row.get(key) != parent.get(key) for key in ("corporate_id", "patient_id")
        ):
            raise RuntimeError(
                f"フォローアップ薬歴 {record_id} の参照先スコープが異なります。"
            )
        if source_id == record_id:
            raise RuntimeError(f"フォローアップ薬歴 {record_id} が自己参照しています。")
        sources[record_id] = source_id

    completed: set[uuid.UUID] = set()
    active: set[uuid.UUID] = set()

    def visit(record_id: uuid.UUID) -> None:
        if record_id in active:
            raise RuntimeError("旧独立フォローアップの参照に循環があります。")
        if record_id in completed:
            return
        active.add(record_id)
        source_id = sources.get(record_id)
        if source_id is not None:
            visit(source_id)
        active.remove(record_id)
        completed.add(record_id)

    for record_id in records:
        visit(record_id)


def _group_legacy_reports(
    records: Mapping[uuid.UUID, Mapping[str, object]],
    children: dict[uuid.UUID, tuple[uuid.UUID, dict[str, object], dict[str, object]]],
) -> dict[uuid.UUID, list[dict[str, object]]]:
    """子ID参照を検証し、親payloadの旧レポートを移行先ごとに分ける。"""
    report_groups: dict[uuid.UUID, list[dict[str, object]]] = {
        child_id: [] for child_id in children
    }
    seen_by_parent: dict[uuid.UUID, set[uuid.UUID]] = {}
    for parent_id, row in records.items():
        payload = _mapping(row["payload"], "薬歴payload")
        reports = payload.get("tracing_reports", [])
        if not isinstance(reports, list):
            raise RuntimeError(
                f"薬歴 {parent_id} のtracing_reportsが配列ではありません。"
            )
        seen = seen_by_parent.setdefault(parent_id, set())
        for item in reports:
            report = dict(_mapping(item, f"薬歴 {parent_id} のtracing_report"))
            report_id = _uuid(report.get("id"), "トレーシングレポートID")
            if report_id in seen:
                raise RuntimeError(
                    f"薬歴 {parent_id} 内でトレーシングレポートIDが重複しています。"
                )
            seen.add(report_id)
            follow_up_id = report.pop("follow_up_id", None)
            if follow_up_id is None:
                continue
            child_id = _uuid(follow_up_id, "トレーシングレポートの旧フォローアップID")
            target = children.get(child_id)
            if target is None or target[0] != parent_id:
                raise RuntimeError(
                    f"トレーシングレポート {report_id} の旧フォローアップ参照が曖昧です。"
                )
            report_groups[child_id].append(report)
    return report_groups


def _load_reception_links(
    records: Mapping[uuid.UUID, Mapping[str, object]],
) -> dict[uuid.UUID, list[dict[str, object]]]:
    """薬歴IDを保持する受付payloadを検索する。"""
    bind = op.get_bind()
    rows = (
        bind.execute(
            sa.text(
                "SELECT id, corporate_id, store_id, payload FROM receptions "
                "WHERE payload ? 'medication_history_id' FOR UPDATE"
            )
        )
        .mappings()
        .all()
    )
    found: dict[uuid.UUID, list[dict[str, object]]] = {}
    known_ids = set(records)
    for raw_row in rows:
        row = dict(cast(Mapping[str, object], raw_row))
        payload = _mapping(row["payload"], "Reception payload")
        raw_history_id = payload.get("medication_history_id")
        if raw_history_id is None:
            continue
        history_id = _uuid(raw_history_id, "受付の薬歴ID")
        if history_id not in known_ids:
            raise RuntimeError(f"受付 {row['id']} が存在しない薬歴を参照しています。")
        found.setdefault(history_id, []).append(row)
    return found


def _validate_reception_links(
    records: Mapping[uuid.UUID, Mapping[str, object]],
    receptions: Mapping[uuid.UUID, Sequence[Mapping[str, object]]],
) -> dict[uuid.UUID, Mapping[str, object]]:
    """Receptionと薬歴の患者・店舗・処方・調剤が曖昧なく一致するか確認する。"""
    linked: dict[uuid.UUID, Mapping[str, object]] = {}
    for record_id, candidates in receptions.items():
        if len(candidates) != 1:
            raise RuntimeError(
                f"薬歴 {record_id} に複数のReceptionが関連付いています。"
            )
        row = records[record_id]
        reception = candidates[0]
        payload = _mapping(reception["payload"], "Reception payload")
        if row.get("record_kind") != "initial":
            raise RuntimeError(
                f"フォローアップ薬歴 {record_id} がReception直結になっています。"
            )
        for key in (
            "corporate_id",
            "store_id",
            "patient_id",
            "prescription_id",
            "dispensing_id",
        ):
            if str(row.get(key)) != str(payload.get(key)):
                raise RuntimeError(
                    f"薬歴 {record_id} とReception {reception['id']} の{key}が一致しません。"
                )
        linked[record_id] = reception
    return linked


def _build_parent_events(
    records: Mapping[uuid.UUID, Mapping[str, object]],
    event_ids: Mapping[uuid.UUID, uuid.UUID],
    event_type_ids: Mapping[str, uuid.UUID],
    migrated_at: datetime,
    reception_links: Mapping[uuid.UUID, Mapping[str, object]],
) -> dict[uuid.UUID, dict[str, object]]:
    """旧独立薬歴1件ごとのEvent行を組み立てる。"""
    event_rows: dict[uuid.UUID, dict[str, object]] = {}
    for record_id, row in records.items():
        is_follow_up = row.get("record_kind") == "follow_up"
        code = _FOLLOW_UP_EVENT if is_follow_up else _PRESCRIPTION_EVENT
        event_id = event_ids[record_id]
        reception = reception_links.get(record_id)
        reception_id = _uuid(reception["id"], "Reception ID") if reception else None
        source_id = (
            _uuid(row["source_record_id"], "参照元薬歴ID") if is_follow_up else None
        )
        occurred_at = (
            _optional_timestamp(row.get("counseled_at")) if is_follow_up else None
        )
        event_rows[record_id] = _event_row(
            event_id=event_id,
            event_type_id=event_type_ids[code],
            event_type_standard_code=code,
            event_type_name=dict(_STANDARD_DEFINITIONS)[code],
            corporate_id=_uuid(row["corporate_id"], "法人ID"),
            store_id=_uuid(row["store_id"], "店舗ID"),
            patient_id=_uuid(row["patient_id"], "患者ID"),
            occurred_at=occurred_at,
            created_at=migrated_at,
            related_event_id=(event_ids[source_id] if source_id is not None else None),
            reception_id=reception_id,
            prescription_id=(
                _uuid(row["prescription_id"], "処方箋ID") if not is_follow_up else None
            ),
            dispensing_id=(
                _uuid(row["dispensing_id"], "調剤ID") if not is_follow_up else None
            ),
        )
    return event_rows


def _build_child_events(
    children: Mapping[
        uuid.UUID, tuple[uuid.UUID, dict[str, object], dict[str, object]]
    ],
    event_ids: Mapping[uuid.UUID, uuid.UUID],
    child_event_ids: Mapping[uuid.UUID, uuid.UUID],
    event_type_ids: Mapping[str, uuid.UUID],
    migrated_at: datetime,
) -> dict[uuid.UUID, dict[str, object]]:
    """旧入れ子FollowUpRecordを親Eventに関連するEvent行へ変換する。"""
    child_rows: dict[uuid.UUID, dict[str, object]] = {}
    code = _FOLLOW_UP_EVENT
    for child_id, (parent_id, child, _unused) in children.items():
        parent_row = _load_parent_row(parent_id)
        child_time = _optional_timestamp(child.get("followed_up_at"))
        if child_time is None:
            raise RuntimeError(
                f"旧フォローアップ {child_id} の指導日時が無いため移行できません。"
            )
        if child.get("counselor_id") is None:
            raise RuntimeError(
                f"旧フォローアップ {child_id} の指導者が無いため移行できません。"
            )
        child_rows[child_id] = _event_row(
            event_id=child_event_ids[child_id],
            event_type_id=event_type_ids[code],
            event_type_standard_code=code,
            event_type_name=dict(_STANDARD_DEFINITIONS)[code],
            corporate_id=_uuid(parent_row["corporate_id"], "法人ID"),
            store_id=_uuid(parent_row["store_id"], "店舗ID"),
            patient_id=_uuid(parent_row["patient_id"], "患者ID"),
            occurred_at=child_time,
            created_at=migrated_at,
            related_event_id=event_ids[parent_id],
            reception_id=None,
            prescription_id=None,
            dispensing_id=None,
        )
    return child_rows


def _load_parent_row(parent_id: uuid.UUID) -> Mapping[str, object]:
    """子行の親スコープを読み戻す。移行トランザクション内で使用する。"""
    row = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT corporate_id, store_id, patient_id FROM medication_history_records "
                "WHERE id = :id"
            ),
            {"id": parent_id},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise RuntimeError(f"旧フォローアップの親薬歴 {parent_id} が見つかりません。")
    return cast(Mapping[str, object], row)


def _event_row(
    *,
    event_id: uuid.UUID,
    event_type_id: uuid.UUID,
    event_type_standard_code: str,
    event_type_name: str,
    corporate_id: uuid.UUID,
    store_id: uuid.UUID,
    patient_id: uuid.UUID,
    occurred_at: datetime | None,
    created_at: datetime,
    related_event_id: uuid.UUID | None,
    reception_id: uuid.UUID | None,
    prescription_id: uuid.UUID | None,
    dispensing_id: uuid.UUID | None,
) -> dict[str, object]:
    """Eventのpayloadと検索列を同じ入力から生成する。"""
    payload: dict[str, object] = {
        "id": str(event_id),
        "event_type_id": str(event_type_id),
        "event_definition_corporate_id": None,
        "event_type_standard_code": event_type_standard_code,
        "event_type_name": event_type_name,
        "corporate_id": str(corporate_id),
        "store_id": str(store_id),
        "patient_id": str(patient_id),
        "occurred_at": occurred_at.isoformat() if occurred_at is not None else None,
        "created_at": created_at.isoformat(),
        "related_event_id": str(related_event_id) if related_event_id else None,
        "reception_id": str(reception_id) if reception_id else None,
        "prescription_id": str(prescription_id) if prescription_id else None,
        "dispensing_id": str(dispensing_id) if dispensing_id else None,
    }
    return {
        **payload,
        "event_type_id": event_type_id,
        "event_definition_corporate_id": None,
        "event_type_standard_code": event_type_standard_code,
        "event_type_name": event_type_name,
        "corporate_id": corporate_id,
        "store_id": store_id,
        "patient_id": patient_id,
        "occurred_at": occurred_at,
        "occurred_at_is_unknown": occurred_at is None,
        "created_at": created_at,
        "related_event_id": related_event_id,
        "reception_id": reception_id,
        "prescription_id": prescription_id,
        "dispensing_id": dispensing_id,
        "payload": payload,
        "version": 1,
        "updated_at": created_at,
    }


def _topological_events(
    parents: Mapping[uuid.UUID, dict[str, object]],
    children: Mapping[uuid.UUID, dict[str, object]],
    records: Mapping[uuid.UUID, Mapping[str, object]],
) -> list[dict[str, object]]:
    """参照元Eventを先に挿入して即時自己外部キーを満たす。"""
    ordered: list[dict[str, object]] = []
    complete: set[uuid.UUID] = set()

    def append_parent(record_id: uuid.UUID) -> None:
        if record_id in complete:
            return
        row = records[record_id]
        source = row.get("source_record_id")
        if source is not None:
            append_parent(_uuid(source, "参照元薬歴ID"))
        ordered.append(parents[record_id])
        complete.add(record_id)

    for record_id in records:
        append_parent(record_id)
    ordered.extend(children.values())
    return ordered


def _archive_and_update_histories(
    records: Mapping[uuid.UUID, Mapping[str, object]],
    children: Mapping[
        uuid.UUID, tuple[uuid.UUID, dict[str, object], dict[str, object]]
    ],
    event_ids: Mapping[uuid.UUID, uuid.UUID],
    child_event_ids: Mapping[uuid.UUID, uuid.UUID],
    migrated_at: datetime,
    report_groups: Mapping[uuid.UUID, list[dict[str, object]]],
    receptions: Mapping[uuid.UUID, Sequence[Mapping[str, object]]],
    reception_for_record: Mapping[uuid.UUID, Mapping[str, object]],
) -> None:
    """元payloadを退避して薬歴・Receptionのlive payloadを新形式にする。"""
    bind = op.get_bind()
    archive_table = sa.table(
        "medication_history_legacy_archives",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("legacy_record_id", postgresql.UUID(as_uuid=True)),
        sa.column("legacy_parent_record_id", postgresql.UUID(as_uuid=True)),
        sa.column("corporate_id", postgresql.UUID(as_uuid=True)),
        sa.column("store_id", postgresql.UUID(as_uuid=True)),
        sa.column("patient_id", postgresql.UUID(as_uuid=True)),
        sa.column("event_id", postgresql.UUID(as_uuid=True)),
        sa.column("archive_kind", sa.String()),
        sa.column("original_payload", postgresql.JSONB()),
        sa.column("archived_at", sa.DateTime(timezone=True)),
    )
    report_link_table = sa.table(
        "legacy_tracing_report_links",
        sa.column("corporate_id", postgresql.UUID(as_uuid=True)),
        sa.column("legacy_parent_record_id", postgresql.UUID(as_uuid=True)),
        sa.column("legacy_tracing_report_id", postgresql.UUID(as_uuid=True)),
        sa.column("target_record_id", postgresql.UUID(as_uuid=True)),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    for record_id, row in records.items():
        original = _mapping(row["payload"], "薬歴payload")
        kind = cast(str, row["record_kind"])
        reception = reception_for_record.get(record_id)
        event_id = event_ids[record_id]
        bind.execute(
            archive_table.insert().values(
                id=uuid.uuid7(),
                legacy_record_id=record_id,
                legacy_parent_record_id=None,
                corporate_id=row["corporate_id"],
                store_id=row["store_id"],
                patient_id=row["patient_id"],
                event_id=event_id,
                archive_kind="record",
                original_payload=original,
                archived_at=migrated_at,
            )
        )
        parent_payload = dict(original)
        parent_payload.update({"event_id": str(event_id)})
        for key in ("record_kind", "source_record_id", "follow_ups"):
            parent_payload.pop(key, None)
        parent_reports = parent_payload.get("tracing_reports", [])
        if isinstance(parent_reports, list):
            parent_payload["tracing_reports"] = [
                {
                    key: value
                    for key, value in _mapping(item, "TracingReport").items()
                    if key != "follow_up_id"
                }
                for item in parent_reports
                if _mapping(item, "TracingReport").get("follow_up_id") is None
            ]
        history_dispensing_id = row["dispensing_id"] if kind == "initial" else None
        history_prescription_id = row["prescription_id"] if kind == "initial" else None
        parent_payload["dispensing_id"] = (
            str(history_dispensing_id) if history_dispensing_id is not None else None
        )
        parent_payload["prescription_id"] = (
            str(history_prescription_id)
            if history_prescription_id is not None
            else None
        )
        bind.execute(
            sa.text(
                "UPDATE medication_history_records SET event_id = :event_id, "
                "dispensing_id = :dispensing_id, prescription_id = :prescription_id, "
                "payload = :payload WHERE id = :id"
            ).bindparams(sa.bindparam("payload", type_=postgresql.JSONB())),
            {
                "event_id": event_id,
                "dispensing_id": history_dispensing_id,
                "prescription_id": history_prescription_id,
                "payload": parent_payload,
                "id": record_id,
            },
        )
        if reception is not None:
            reception_payload = dict(
                _mapping(reception["payload"], "Reception payload")
            )
            reception_payload["event_id"] = str(event_id)
            bind.execute(
                sa.text(
                    "UPDATE receptions SET event_id = :event_id, payload = :payload "
                    "WHERE corporate_id = :corporate_id AND store_id = :store_id AND id = :id"
                ).bindparams(sa.bindparam("payload", type_=postgresql.JSONB())),
                {
                    "event_id": event_id,
                    "payload": reception_payload,
                    "corporate_id": reception["corporate_id"],
                    "store_id": reception["store_id"],
                    "id": reception["id"],
                },
            )

    for child_id, (parent_id, original_child, _unused) in children.items():
        parent = records[parent_id]
        child = dict(original_child)
        reports = [dict(report) for report in report_groups.get(child_id, [])]
        event_id = child_event_ids[child_id]
        bind.execute(
            archive_table.insert().values(
                id=uuid.uuid7(),
                legacy_record_id=child_id,
                legacy_parent_record_id=parent_id,
                corporate_id=parent["corporate_id"],
                store_id=parent["store_id"],
                patient_id=parent["patient_id"],
                event_id=event_id,
                archive_kind="follow_up",
                original_payload=child,
                archived_at=migrated_at,
            )
        )
        occurrence = _optional_timestamp(child.get("followed_up_at"))
        live_payload = {
            "id": str(child_id),
            "event_id": str(event_id),
            "corporate_id": str(parent["corporate_id"]),
            "store_id": str(parent["store_id"]),
            "patient_id": str(parent["patient_id"]),
            "dispensing_id": None,
            "prescription_id": None,
            "counselor_id": child.get("counselor_id"),
            "counseled_at": occurrence.isoformat() if occurrence is not None else None,
            "method": child.get("method"),
            "soap": child.get("soap"),
            "handbook_status": child.get("handbook_status"),
            "residual_drug": child.get("residual_drug"),
            "information_sheet_provided": child.get(
                "information_sheet_provided", False
            ),
            "profile_updates": child.get("profile_updates", {}),
            "additional_notes": child.get("additional_notes", []),
            "billing_additions": [],
            "source_system": child.get("source_system"),
            "imported_at": None,
            "recorded_by": child.get("recorded_by"),
            "recorded_at": child.get("recorded_at"),
            "status": "legacy_recorded",
            "amendments": [],
            "tracing_reports": reports,
            "finalized_at": None,
            "finalized_by": None,
            "delay_reason": None,
            "review_result": None,
            "retention_expiry_date": None,
            "external_corrections": [],
        }
        bind.execute(
            sa.text(
                "INSERT INTO medication_history_records "
                "(id, corporate_id, store_id, patient_id, event_id, dispensing_id, "
                "prescription_id, record_kind, source_record_id, status, counseled_at, recorded_at, payload, version, "
                "created_at, updated_at) VALUES (:id, :corporate_id, :store_id, :patient_id, "
                ":event_id, NULL, NULL, 'initial', NULL, 'legacy_recorded', :counseled_at, :recorded_at, "
                ":payload, 1, :created_at, :updated_at)"
            ).bindparams(sa.bindparam("payload", type_=postgresql.JSONB())),
            {
                "id": child_id,
                "corporate_id": parent["corporate_id"],
                "store_id": parent["store_id"],
                "patient_id": parent["patient_id"],
                "event_id": event_id,
                "counseled_at": occurrence,
                "recorded_at": _optional_timestamp(child.get("recorded_at")),
                "payload": live_payload,
                "created_at": migrated_at,
                "updated_at": migrated_at,
            },
        )
        for report in reports:
            bind.execute(
                report_link_table.insert().values(
                    corporate_id=parent["corporate_id"],
                    legacy_parent_record_id=parent_id,
                    legacy_tracing_report_id=_uuid(
                        report["id"], "トレーシングレポートID"
                    ),
                    target_record_id=child_id,
                    created_at=migrated_at,
                )
            )


def _optional_timestamp(value: object) -> datetime | None:
    """JSON timestampを読み、時区間情報がない値は推測せず拒否する。"""
    if value is None:
        return None
    parsed = (
        value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    )
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RuntimeError("旧薬歴にタイムゾーンのない日時があり、移行できません。")
    return parsed


def _uuid(value: object, label: str) -> uuid.UUID:
    """UUID値を厳密に解釈する。"""
    try:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError) as error:
        raise RuntimeError(f"{label}がUUIDではありません。") from error


def _mapping(value: object, label: str) -> dict[str, object]:
    """JSONオブジェクトを移行用辞書へ変換する。"""
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise RuntimeError(f"{label}がJSONオブジェクトではありません。")
    return dict(cast(Mapping[str, object], value))


def _create_routines() -> None:
    """Eventと旧形式アーカイブへの不変トリガを設置する。"""
    op.execute(
        """CREATE OR REPLACE FUNCTION protect_care_event_identity() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION '業務Eventは削除できません。' USING ERRCODE = '23514', CONSTRAINT = 'ck_care_events_immutable';
        END IF;
        IF NEW.id IS DISTINCT FROM OLD.id OR NEW.event_type_id IS DISTINCT FROM OLD.event_type_id OR NEW.event_definition_corporate_id IS DISTINCT FROM OLD.event_definition_corporate_id OR NEW.event_type_standard_code IS DISTINCT FROM OLD.event_type_standard_code OR NEW.event_type_name IS DISTINCT FROM OLD.event_type_name OR NEW.corporate_id IS DISTINCT FROM OLD.corporate_id OR NEW.store_id IS DISTINCT FROM OLD.store_id OR NEW.patient_id IS DISTINCT FROM OLD.patient_id OR NEW.created_at IS DISTINCT FROM OLD.created_at OR NEW.related_event_id IS DISTINCT FROM OLD.related_event_id OR NEW.reception_id IS DISTINCT FROM OLD.reception_id OR NEW.prescription_id IS DISTINCT FROM OLD.prescription_id OR NEW.dispensing_id IS DISTINCT FROM OLD.dispensing_id OR (NEW.payload - 'occurred_at') IS DISTINCT FROM (OLD.payload - 'occurred_at') THEN
            RAISE EXCEPTION '業務Eventの内容と参照は変更できません。' USING ERRCODE = '23514', CONSTRAINT = 'ck_care_events_immutable';
        END IF;
        IF OLD.occurred_at_is_unknown AND OLD.occurred_at IS NULL AND NOT NEW.occurred_at_is_unknown AND NEW.occurred_at IS NOT NULL THEN
            RETURN NEW;
        END IF;
        RAISE EXCEPTION '業務Eventの発生日時は時刻不明から一度だけ確定できます。' USING ERRCODE = '23514', CONSTRAINT = 'ck_care_events_immutable';
    END;
    $$"""
    )
    op.execute(
        "CREATE TRIGGER care_events_immutable BEFORE UPDATE OR DELETE ON care_events "
        "FOR EACH ROW EXECUTE FUNCTION protect_care_event_identity()"
    )
    op.execute(
        """CREATE OR REPLACE FUNCTION protect_reception_event_association() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        IF OLD.event_id IS NOT NULL AND NEW.event_id IS DISTINCT FROM OLD.event_id THEN
            RAISE EXCEPTION '受付のEvent関連は付け替えできません。' USING ERRCODE = '23514', CONSTRAINT = 'ck_receptions_event_immutable';
        END IF;
        RETURN NEW;
    END;
    $$"""
    )
    op.execute(
        "CREATE TRIGGER receptions_event_immutable BEFORE UPDATE ON receptions "
        "FOR EACH ROW EXECUTE FUNCTION protect_reception_event_association()"
    )
    op.execute(
        """CREATE OR REPLACE FUNCTION prevent_legacy_archive_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        RAISE EXCEPTION '移行アーカイブは追記専用です。' USING ERRCODE = '23514', CONSTRAINT = 'ck_medication_history_legacy_archive_immutable';
    END;
    $$"""
    )
    op.execute(
        "CREATE TRIGGER medication_history_legacy_archives_immutable BEFORE UPDATE OR DELETE "
        "ON medication_history_legacy_archives FOR EACH ROW EXECUTE FUNCTION prevent_legacy_archive_mutation()"
    )
    op.execute(
        "CREATE TRIGGER legacy_tracing_report_links_immutable BEFORE UPDATE OR DELETE "
        "ON legacy_tracing_report_links FOR EACH ROW EXECUTE FUNCTION prevent_legacy_archive_mutation()"
    )
    op.execute(
        """CREATE OR REPLACE FUNCTION check_care_event_type_scope() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        IF NEW.event_definition_corporate_id IS NULL THEN
            IF NOT EXISTS (
                SELECT 1 FROM event_definitions
                WHERE id = NEW.event_type_id AND corporate_id IS NULL
            ) THEN
                RAISE EXCEPTION '標準Event種別の定義が存在しないか、法人が一致しません。' USING ERRCODE = '23514', CONSTRAINT = 'ck_care_events_event_type_scope';
            END IF;
        ELSE
            IF NOT EXISTS (
                SELECT 1 FROM event_definitions
                WHERE id = NEW.event_type_id AND corporate_id = NEW.corporate_id
            ) THEN
                RAISE EXCEPTION '法人固有Event種別の定義が存在しないか、法人が一致しません。' USING ERRCODE = '23514', CONSTRAINT = 'ck_care_events_event_type_scope';
            END IF;
        END IF;
        RETURN NEW;
    END;
    $$"""
    )
    op.execute(
        "CREATE TRIGGER care_events_event_type_scope_guard BEFORE INSERT OR UPDATE ON care_events "
        "FOR EACH ROW EXECUTE FUNCTION check_care_event_type_scope()"
    )
    op.execute(
        """CREATE OR REPLACE FUNCTION check_care_event_reception_consistency() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE
        v_reception RECORD;
    BEGIN
        IF NEW.reception_id IS NULL THEN
            RETURN NEW;
        END IF;

        SELECT payload
        INTO v_reception
        FROM receptions
        WHERE corporate_id = NEW.corporate_id
          AND store_id = NEW.store_id
          AND id = NEW.reception_id
        FOR KEY SHARE;

        IF NOT FOUND THEN
            RETURN NEW;
        END IF;

        IF NULLIF(v_reception.payload->>'patient_id', '')::uuid IS DISTINCT FROM NEW.patient_id
           OR NULLIF(v_reception.payload->>'prescription_id', '')::uuid IS DISTINCT FROM NEW.prescription_id
           OR NULLIF(v_reception.payload->>'dispensing_id', '')::uuid IS DISTINCT FROM NEW.dispensing_id THEN
            RAISE EXCEPTION '受付と業務Eventの患者・処方・調剤参照が一致しません。' USING ERRCODE = '23514', CONSTRAINT = 'ck_care_events_reception_resources';
        END IF;
        RETURN NEW;
    END;
    $$"""
    )
    op.execute(
        "CREATE TRIGGER care_events_reception_resources_guard BEFORE INSERT OR UPDATE ON care_events "
        "FOR EACH ROW EXECUTE FUNCTION check_care_event_reception_consistency()"
    )
    op.execute(
        """CREATE OR REPLACE FUNCTION check_reception_care_event_consistency() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE
        v_event RECORD;
    BEGIN
        IF NEW.event_id IS NULL THEN
            RETURN NEW;
        END IF;

        SELECT patient_id, prescription_id, dispensing_id
        INTO v_event
        FROM care_events
        WHERE id = NEW.event_id
        FOR KEY SHARE;

        IF NOT FOUND THEN
            RETURN NEW;
        END IF;

        IF NULLIF(NEW.payload->>'patient_id', '')::uuid IS DISTINCT FROM v_event.patient_id
           OR NULLIF(NEW.payload->>'prescription_id', '')::uuid IS DISTINCT FROM v_event.prescription_id
           OR NULLIF(NEW.payload->>'dispensing_id', '')::uuid IS DISTINCT FROM v_event.dispensing_id THEN
            RAISE EXCEPTION '受付と業務Eventの患者・処方・調剤参照が一致しません。' USING ERRCODE = '23514', CONSTRAINT = 'ck_receptions_event_resources';
        END IF;
        RETURN NEW;
    END;
    $$"""
    )
    op.execute(
        "CREATE TRIGGER receptions_event_resources_guard BEFORE INSERT OR UPDATE ON receptions "
        "FOR EACH ROW EXECUTE FUNCTION check_reception_care_event_consistency()"
    )
    op.execute(
        """CREATE OR REPLACE FUNCTION check_medication_history_event_resources() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE
        v_event RECORD;
    BEGIN
        SELECT prescription_id, dispensing_id, corporate_id, store_id, patient_id
        INTO v_event
        FROM care_events
        WHERE id = NEW.event_id;

        IF NOT FOUND THEN
            RAISE EXCEPTION '関連する業務Eventが存在しません。' USING ERRCODE = '23503', CONSTRAINT = 'fk_medication_history_records_event_scope';
        END IF;

        IF NEW.corporate_id IS DISTINCT FROM v_event.corporate_id
           OR NEW.store_id IS DISTINCT FROM v_event.store_id
           OR NEW.patient_id IS DISTINCT FROM v_event.patient_id THEN
            RAISE EXCEPTION '薬歴と業務Eventの所属範囲が一致しません。' USING ERRCODE = '23514', CONSTRAINT = 'ck_medication_history_records_event_scope';
        END IF;

        IF NEW.prescription_id IS DISTINCT FROM v_event.prescription_id
           OR NEW.dispensing_id IS DISTINCT FROM v_event.dispensing_id THEN
            RAISE EXCEPTION '薬歴と業務Eventの処方・調剤参照が一致しません。' USING ERRCODE = '23514', CONSTRAINT = 'ck_medication_history_records_event_resources';
        END IF;

        RETURN NEW;
    END;
    $$"""
    )
    op.execute(
        "CREATE TRIGGER medication_history_event_resources_guard BEFORE INSERT OR UPDATE ON medication_history_records "
        "FOR EACH ROW EXECUTE FUNCTION check_medication_history_event_resources()"
    )


def _drop_routines() -> None:
    """downgrade guard通過後にmigration専用Routineを削除する。"""
    op.execute(
        "DROP TRIGGER medication_history_event_resources_guard ON medication_history_records"
    )
    op.execute("DROP TRIGGER receptions_event_resources_guard ON receptions")
    op.execute("DROP TRIGGER care_events_reception_resources_guard ON care_events")
    op.execute("DROP TRIGGER care_events_event_type_scope_guard ON care_events")
    op.execute(
        "DROP TRIGGER legacy_tracing_report_links_immutable ON legacy_tracing_report_links"
    )
    op.execute(
        "DROP TRIGGER medication_history_legacy_archives_immutable ON medication_history_legacy_archives"
    )
    op.execute("DROP TRIGGER receptions_event_immutable ON receptions")
    op.execute("DROP TRIGGER care_events_immutable ON care_events")
    op.execute("DROP FUNCTION check_medication_history_event_resources()")
    op.execute("DROP FUNCTION check_reception_care_event_consistency()")
    op.execute("DROP FUNCTION check_care_event_reception_consistency()")
    op.execute("DROP FUNCTION check_care_event_type_scope()")
    op.execute("DROP FUNCTION prevent_legacy_archive_mutation()")
    op.execute("DROP FUNCTION protect_reception_event_association()")
    op.execute("DROP FUNCTION protect_care_event_identity()")
