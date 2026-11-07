"""法人ログイン用の6桁コードを追加する。"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "20261108_0020"
down_revision: str | None = "20261107_0019"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """既存法人へコードを割り当て、一意制約を追加する。"""
    op.execute(
        "CREATE SEQUENCE corporate_login_codes MINVALUE 0 MAXVALUE 999999 START 0"
    )
    op.add_column(
        "corporates", sa.Column("login_code", sa.String(length=6), nullable=True)
    )
    op.execute(
        """WITH numbered AS (
            SELECT id, row_number() OVER (ORDER BY id) - 1 AS number FROM corporates
        ) UPDATE corporates SET login_code = lpad(numbered.number::text, 6, '0')
        FROM numbered WHERE corporates.id = numbered.id"""
    )
    op.execute(
        "UPDATE corporates SET payload = jsonb_set(payload, '{login_code}', to_jsonb(login_code), true)"
    )
    op.alter_column("corporates", "login_code", nullable=False)
    op.execute(
        "SELECT setval('corporate_login_codes', COALESCE((SELECT max(login_code::integer) FROM corporates), 0), EXISTS (SELECT 1 FROM corporates))"
    )
    op.create_unique_constraint(
        "uq_corporates_login_code", "corporates", ["login_code"]
    )
    op.create_check_constraint(
        "ck_corporates_login_code_six_digits",
        "corporates",
        "login_code ~ '^[0-9]{6}$'",
    )


def downgrade() -> None:
    """法人ログインコードを削除する。"""
    op.execute("UPDATE corporates SET payload = payload - 'login_code'")
    op.drop_constraint(
        "ck_corporates_login_code_six_digits", "corporates", type_="check"
    )
    op.drop_constraint("uq_corporates_login_code", "corporates", type_="unique")
    op.drop_column("corporates", "login_code")
    op.execute("DROP SEQUENCE corporate_login_codes")
