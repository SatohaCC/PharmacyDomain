"""ローカル認証セッションへ選択店舗ID列を追加する。"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261031_0016"
down_revision: str | None = "20261031_0015"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "local_sessions",
        sa.Column("selected_store_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_local_sessions_selected_store_id_stores",
        "local_sessions",
        "stores",
        ["selected_store_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_local_sessions_selected_store_id_stores",
        "local_sessions",
        type_="foreignkey",
    )
    op.drop_column("local_sessions", "selected_store_id")
