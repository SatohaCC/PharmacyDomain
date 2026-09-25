"""NSIPS受付指紋と店舗スコープ患者IDを永続化する。"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260923_0005"
down_revision: str | None = "20260920_0004"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """受付集約を追加し、患者外部IDの一意範囲を店舗単位にする。"""
    op.add_column(
        "patient_external_identifiers",
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.drop_index(
        "uq_patient_external_identifiers_active_source",
        table_name="patient_external_identifiers",
    )
    op.create_index(
        "uq_patient_external_identifiers_active_source",
        "patient_external_identifiers",
        ["corporate_id", "store_id", "system_name", "external_patient_id"],
        unique=True,
        postgresql_where=sa.text("is_active AND store_id IS NOT NULL"),
    )
    op.create_index(
        "uq_patient_external_identifiers_active_legacy_source",
        "patient_external_identifiers",
        ["corporate_id", "system_name", "external_patient_id"],
        unique=True,
        postgresql_where=sa.text("is_active AND store_id IS NULL"),
    )
    op.create_table(
        "receptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("corporate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_receptions"),
    )
    op.create_index(
        "ix_receptions_corporate_store",
        "receptions",
        ["corporate_id", "store_id"],
    )


def downgrade() -> None:
    """受付集約を削除し、患者外部IDの旧一意範囲へ戻す。"""
    op.drop_table("receptions")
    op.drop_index(
        "uq_patient_external_identifiers_active_source",
        table_name="patient_external_identifiers",
    )
    op.drop_index(
        "uq_patient_external_identifiers_active_legacy_source",
        table_name="patient_external_identifiers",
    )
    op.drop_column("patient_external_identifiers", "store_id")
    op.create_index(
        "uq_patient_external_identifiers_active_source",
        "patient_external_identifiers",
        ["corporate_id", "system_name", "external_patient_id"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )
