"""NSIPSファイル取込台帳テーブルを追加する。"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261107_0019"
down_revision: str | None = "20261102_0018"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """nsips_files テーブルを作成する。"""
    op.create_table(
        "nsips_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("corporate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_id", sa.String(length=128), nullable=False),
        sa.Column("file_name", sa.String(length=256), nullable=False),
        sa.Column("operation", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("raw_payload", sa.Text(), nullable=False),
        sa.Column("target_reception_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_text", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_nsips_files"),
        sa.UniqueConstraint(
            "corporate_id",
            "store_id",
            "file_id",
            "operation",
            name="uq_nsips_files_identity",
        ),
    )
    op.create_index(
        "ix_nsips_files_applied",
        "nsips_files",
        ["corporate_id", "store_id", "file_id", "status"],
    )


def downgrade() -> None:
    """nsips_files テーブルを削除する。"""
    op.drop_index("ix_nsips_files_applied", table_name="nsips_files")
    op.drop_table("nsips_files")
