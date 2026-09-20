"""薬歴記載区分カタログ集約の永続化。"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260920_0004"
down_revision: str | None = "20260917_0003"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """薬歴記載区分カタログ集約のテーブルを作成する。"""
    op.create_table(
        "medication_history_category_catalogs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("corporate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_medication_history_category_catalogs"),
        sa.UniqueConstraint(
            "corporate_id", name="uq_medication_history_category_catalogs_corporate"
        ),
    )


def downgrade() -> None:
    """薬歴記載区分カタログ集約のテーブルを削除する。"""
    op.drop_table("medication_history_category_catalogs")
