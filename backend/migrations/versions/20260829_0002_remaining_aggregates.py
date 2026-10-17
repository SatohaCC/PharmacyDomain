"""残る集約（店舗・スタッフ・患者・資格・受付・薬歴・医薬品マスタ）の永続化。

期間の重なりは一意制約では表せないため、患者資格と医薬品マスタには排他制約を使う。
排他制約の中で uuid や整数を等値比較するには ``btree_gist`` 拡張が要る。
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260829_0002"
down_revision: str | None = "20260829_0001"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """排他制約用の拡張を有効にしてから、残る集約のテーブルを作成する。"""
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    op.create_table(
        "stores",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("corporate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=True),
        sa.Column("insurance_pharmacy_number", sa.String(length=32), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["corporate_id"],
            ["corporates.id"],
            name="fk_stores_corporate_id_corporates",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_stores"),
        sa.UniqueConstraint("corporate_id", "name", name="uq_stores_corporate_name"),
    )
    op.create_index("ix_stores_corporate_id", "stores", ["corporate_id"])
    op.create_index(
        "uq_stores_corporate_code",
        "stores",
        ["corporate_id", "code"],
        unique=True,
        postgresql_where=sa.text("code IS NOT NULL"),
    )
    op.create_index(
        "uq_stores_insurance_pharmacy_number",
        "stores",
        ["insurance_pharmacy_number"],
        unique=True,
        postgresql_where=sa.text("insurance_pharmacy_number IS NOT NULL"),
    )

    op.create_table(
        "staff_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("corporate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["corporate_id"],
            ["corporates.id"],
            name="fk_staff_members_corporate_id_corporates",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_staff_members"),
    )
    op.create_index("ix_staff_members_corporate_id", "staff_members", ["corporate_id"])
    # スタッフコードは無効化後も再利用させないので is_active では絞らない。
    op.create_index(
        "uq_staff_members_corporate_code",
        "staff_members",
        ["corporate_id", "code"],
        unique=True,
        postgresql_where=sa.text("code IS NOT NULL"),
    )

    op.create_table(
        "patients",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("corporate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patient_number", sa.Integer(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_patients"),
        sa.UniqueConstraint(
            "corporate_id", "patient_number", name="uq_patients_corporate_number"
        ),
    )
    op.create_index("ix_patients_corporate_id", "patients", ["corporate_id"])

    op.create_table(
        "patient_number_sequences",
        sa.Column("corporate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("last_number", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("corporate_id", name="pk_patient_number_sequences"),
    )

    op.create_table(
        "patient_external_identifiers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("corporate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("system_name", sa.String(length=200), nullable=False),
        sa.Column("external_patient_id", sa.String(length=200), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_patient_external_identifiers"),
    )
    op.create_index(
        "ix_patient_external_identifiers_corporate_patient",
        "patient_external_identifiers",
        ["corporate_id", "patient_id"],
    )
    # 一意とみなすのは有効な行だけ。無効化してから別患者へ付け替えられるようにする。
    op.create_index(
        "uq_patient_external_identifiers_active_source",
        "patient_external_identifiers",
        ["corporate_id", "system_name", "external_patient_id"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )

    op.create_table(
        "patient_coverages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("corporate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("coverage_type", sa.String(length=32), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("effective_range", postgresql.DATERANGE(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_patient_coverages"),
        postgresql.ExcludeConstraint(
            ("corporate_id", "="),
            ("patient_id", "="),
            ("coverage_type", "="),
            ("priority", "="),
            ("effective_range", "&&"),
            name="excl_patient_coverages_effective_period",
            using="gist",
            where=sa.text("effective_range IS NOT NULL"),
        ),
    )
    op.create_index(
        "ix_patient_coverages_corporate_patient",
        "patient_coverages",
        ["corporate_id", "patient_id"],
    )

    op.create_table(
        "coverage_selection_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("corporate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("applied_on", sa.Date(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_coverage_selection_records"),
    )
    op.create_index(
        "ix_coverage_selection_records_latest",
        "coverage_selection_records",
        ["corporate_id", "store_id", "patient_id", "recorded_at", "id"],
    )

    op.create_table(
        "medication_history_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("corporate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dispensing_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("prescription_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("counseled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_medication_history_records"),
    )
    op.create_index(
        "ix_medication_history_records_corporate_patient",
        "medication_history_records",
        ["corporate_id", "patient_id", "counseled_at"],
    )
    # 確定済だけを1件に制限する。下書きは複数持つのが正当なので対象外。
    op.create_index(
        "uq_medication_history_records_finalized_dispensing",
        "medication_history_records",
        ["corporate_id", "dispensing_id"],
        unique=True,
        postgresql_where=sa.text("status = 'finalized'"),
    )

    op.create_table(
        "patient_medical_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("corporate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_patient_medical_profiles"),
        sa.UniqueConstraint(
            "corporate_id", "patient_id", name="uq_patient_medical_profiles_patient"
        ),
    )

    op.create_table(
        "medicines",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("identifier_key", sa.String(length=80), nullable=False),
        sa.Column("code_type", sa.String(length=32), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=True),
        sa.Column("listed_on", sa.Date(), nullable=False),
        sa.Column("withdrawn_on", sa.Date(), nullable=True),
        sa.Column("effective_range", postgresql.DATERANGE(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_medicines"),
        postgresql.ExcludeConstraint(
            ("identifier_key", "="),
            ("effective_range", "&&"),
            name="excl_medicines_effective_period",
            using="gist",
        ),
    )
    op.create_index(
        "ix_medicines_identifier_listed_on",
        "medicines",
        ["identifier_key", "listed_on"],
    )


def downgrade() -> None:
    """作成順の逆にテーブルを削除する。拡張は他が使いうるので残す。"""
    op.drop_table("medicines")
    op.drop_table("patient_medical_profiles")
    op.drop_table("medication_history_records")
    op.drop_table("coverage_selection_records")
    op.drop_table("patient_coverages")
    op.drop_table("patient_external_identifiers")
    op.drop_table("patient_number_sequences")
    op.drop_table("patients")
    op.drop_table("staff_members")
    op.drop_table("stores")
