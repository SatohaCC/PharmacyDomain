"""外部訂正検索用の薬歴JSONB GIN索引を追加する。"""

from __future__ import annotations

from alembic import op

revision: str = "20260927_0011"
down_revision: str | None = "20260927_0010"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """JSONPathの訂正状態検索用索引を作る。"""
    op.create_index(
        "ix_medication_history_records_payload_jsonpath",
        "medication_history_records",
        ["payload"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"payload": "jsonb_path_ops"},
    )


def downgrade() -> None:
    """外部訂正検索用索引を削除する。"""
    op.drop_index(
        "ix_medication_history_records_payload_jsonpath",
        table_name="medication_history_records",
    )
