"""薬歴に登録日時の検索列を追加する。"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "20260926_0009"
down_revision: str | None = "20260926_0008"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """既存行の登録時刻を推定せず、NULL可能な列を追加する。"""
    op.add_column(
        "medication_history_records",
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """登録日時検索列だけを削除し、payloadの履歴は保持する。"""
    op.drop_column("medication_history_records", "recorded_at")
