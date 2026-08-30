"""調剤完了縦切りの PostgreSQL 永続化テーブル。"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260829_0001"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """初回の集約 payload テーブルと検索制約を作成する。"""
    op.create_table(
        "corporates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("representative_name", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_corporates"),
        sa.UniqueConstraint("name", name="uq_corporates_name"),
    )
    op.create_table(
        "prescriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("corporate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("document_number", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_prescriptions"),
    )
    op.create_index(
        "uq_prescriptions_electronic_document_number",
        "prescriptions",
        ["corporate_id", "document_number"],
        unique=True,
        postgresql_where=sa.text("source_type = 'electronic'"),
    )
    op.create_index(
        "ix_prescriptions_corporate_patient",
        "prescriptions",
        ["corporate_id", "patient_id"],
    )
    op.create_table(
        "dispensing_processes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("corporate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("prescription_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("iteration", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_dispensing_processes"),
        sa.UniqueConstraint(
            "corporate_id",
            "prescription_id",
            "iteration",
            name="uq_dispensing_processes_prescription_iteration",
        ),
    )
    op.create_index(
        "ix_dispensing_processes_corporate_prescription",
        "dispensing_processes",
        ["corporate_id", "prescription_id"],
    )


def downgrade() -> None:
    """初回テーブルを作成順の逆に削除する。"""
    op.drop_index(
        "ix_dispensing_processes_corporate_prescription",
        table_name="dispensing_processes",
    )
    op.drop_table("dispensing_processes")
    op.drop_index("ix_prescriptions_corporate_patient", table_name="prescriptions")
    op.drop_index(
        "uq_prescriptions_electronic_document_number",
        table_name="prescriptions",
    )
    op.drop_table("prescriptions")
    op.drop_table("corporates")
