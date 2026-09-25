"""NSIPS取込だけの薬歴下書きを保存できるようにする。"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "20260925_0007"
down_revision: str | None = "20260923_0006"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """薬歴の指導日時列をNULL可能にする。"""
    op.alter_column(
        "medication_history_records",
        "counseled_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
    )


def downgrade() -> None:
    """取込時刻だけの下書きが残る間はNOT NULLへ戻さない。"""
    if not op.get_context().as_sql:
        has_undated_records = (
            op.get_bind()
            .execute(
                sa.text(
                    "SELECT EXISTS ("
                    "SELECT 1 FROM medication_history_records "
                    "WHERE counseled_at IS NULL"
                    ")"
                )
            )
            .scalar_one()
        )
        if has_undated_records:
            raise RuntimeError(
                "未確定の薬歴が残っているため指導日時をNOT NULLへ戻せません。"
            )
    op.alter_column(
        "medication_history_records",
        "counseled_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )
