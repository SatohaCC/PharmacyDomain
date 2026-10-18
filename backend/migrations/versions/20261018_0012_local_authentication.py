"""ローカル認証の資格情報と期限付きセッションを追加する。"""

import sqlalchemy as sa
from alembic import op

revision: str = "20261018_0012"
down_revision: str | None = "20260927_0011"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """資格情報とセッションを業務集約から分離して作成する。"""
    op.create_table(
        "local_credentials",
        sa.Column("login_id", sa.String(64), nullable=False),
        sa.Column(
            "subject",
            sa.String(1000),
            sa.ForeignKey(
                "user_accounts.external_subject",
                name="fk_local_credentials_subject_user_accounts",
            ),
            nullable=False,
        ),
        sa.Column("password_hash", sa.String(256), nullable=False),
        sa.Column("must_change", sa.Boolean(), nullable=False),
        sa.Column("failed_attempts", sa.Integer(), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("login_id", name="pk_local_credentials"),
        sa.UniqueConstraint("subject", name="uq_local_credentials_subject"),
    )
    op.create_table(
        "local_sessions",
        sa.Column("digest", sa.String(64), nullable=False),
        sa.Column(
            "subject",
            sa.String(1000),
            sa.ForeignKey(
                "local_credentials.subject",
                name="fk_local_sessions_subject_local_credentials",
            ),
            nullable=False,
        ),
        sa.Column("restricted", sa.Boolean(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("digest", name="pk_local_sessions"),
    )


def downgrade() -> None:
    """認証の技術状態だけを削除する。"""
    op.drop_table("local_sessions")
    op.drop_table("local_credentials")
