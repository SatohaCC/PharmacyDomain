"""薬歴に独立フォローアップ種別と参照元を追加する。"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "20260926_0008"
down_revision: str | None = "20260925_0007"
branch_labels: str | None = None
depends_on: str | None = None

_TABLE = "medication_history_records"
_UNIQUE_INDEX = "uq_medication_history_records_finalized_dispensing"
_SOURCE_UNIQUE = "uq_medication_history_records_source_identity"
_SOURCE_FK = "fk_medication_history_records_source_identity"
_KIND_CHECK = "ck_medication_history_records_record_kind_source"


def upgrade() -> None:
    """既存薬歴を初回として保ち、参照鎖と初回だけの一意性を追加する。"""
    op.add_column(
        _TABLE,
        sa.Column(
            "record_kind",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'initial'"),
        ),
    )
    op.alter_column(_TABLE, "record_kind", server_default=None)
    op.add_column(
        _TABLE,
        sa.Column("source_record_id", sa.Uuid(), nullable=True),
    )
    op.create_unique_constraint(
        _SOURCE_UNIQUE,
        _TABLE,
        ["id", "corporate_id", "patient_id", "prescription_id", "dispensing_id"],
    )
    op.create_foreign_key(
        _SOURCE_FK,
        _TABLE,
        _TABLE,
        [
            "source_record_id",
            "corporate_id",
            "patient_id",
            "prescription_id",
            "dispensing_id",
        ],
        ["id", "corporate_id", "patient_id", "prescription_id", "dispensing_id"],
    )
    op.create_check_constraint(
        _KIND_CHECK,
        _TABLE,
        "(record_kind = 'initial' AND source_record_id IS NULL) OR "
        "(record_kind = 'follow_up' AND source_record_id IS NOT NULL "
        "AND source_record_id <> id)",
    )
    op.drop_index(_UNIQUE_INDEX, table_name=_TABLE)
    op.create_index(
        _UNIQUE_INDEX,
        _TABLE,
        ["corporate_id", "dispensing_id"],
        unique=True,
        postgresql_where=sa.text("status = 'finalized' AND record_kind = 'initial'"),
    )


def downgrade() -> None:
    """フォローアップ行を失わずに旧一意性へ戻せる場合だけ戻す。"""
    if op.get_context().as_sql:
        op.execute(
            "DO $$ BEGIN "
            f"IF EXISTS (SELECT 1 FROM {_TABLE} WHERE record_kind = 'follow_up') "
            "THEN RAISE EXCEPTION "
            "'フォローアップ薬歴が残っているため旧スキーマへ戻せません。'; "
            "END IF; END $$"
        )
    else:
        has_follow_up_records = (
            op.get_bind()
            .execute(
                sa.text(
                    f"SELECT EXISTS (SELECT 1 FROM {_TABLE} "
                    "WHERE record_kind = 'follow_up')"
                )
            )
            .scalar_one()
        )
        if has_follow_up_records:
            raise RuntimeError(
                "フォローアップ薬歴が残っているため旧スキーマへ戻せません。"
            )
    op.drop_index(_UNIQUE_INDEX, table_name=_TABLE)
    op.create_index(
        _UNIQUE_INDEX,
        _TABLE,
        ["corporate_id", "dispensing_id"],
        unique=True,
        postgresql_where=sa.text("status = 'finalized'"),
    )
    op.drop_constraint(_KIND_CHECK, _TABLE, type_="check")
    op.drop_constraint(_SOURCE_FK, _TABLE, type_="foreignkey")
    op.drop_constraint(_SOURCE_UNIQUE, _TABLE, type_="unique")
    op.drop_column(_TABLE, "source_record_id")
    op.drop_column(_TABLE, "record_kind")
