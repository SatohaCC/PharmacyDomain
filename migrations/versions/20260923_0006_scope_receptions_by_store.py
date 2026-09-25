"""受付の主キーを法人・店舗・受付IDの組へ変更する。"""

from __future__ import annotations

from alembic import op

revision: str = "20260923_0006"
down_revision: str | None = "20260923_0005"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """別店舗間で同じ受付IDを使える複合主キーへ移行する。"""
    op.drop_constraint("pk_receptions", "receptions", type_="primary")
    op.create_primary_key(
        "pk_receptions",
        "receptions",
        ["corporate_id", "store_id", "id"],
    )


def downgrade() -> None:
    """受付IDの重複があればDB制約で拒否される旧い主キーへ戻す。"""
    op.drop_constraint("pk_receptions", "receptions", type_="primary")
    op.create_primary_key("pk_receptions", "receptions", ["id"])
