"""認証資格情報の法人スコープ化、運営者専用テーブル新設、および招待機能テーブル削除。"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261031_0015"
down_revision: str | None = "20261031_0014"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # 1. user_invitations の削除
    op.drop_table("user_invitations")

    # 2. vendor_operators テーブルの新設
    op.create_table(
        "vendor_operators",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(256), nullable=False),
        sa.Column("external_subject", sa.String(1000), nullable=False),
        sa.Column(
            "failed_attempts",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_vendor_operators"),
        sa.UniqueConstraint("email", name="uq_vendor_operators_email"),
        sa.UniqueConstraint(
            "external_subject", name="uq_vendor_operators_external_subject"
        ),
    )

    # 3. operation_audits の更新（運営者FK、NULL許可、整合制約）
    op.add_column(
        "operation_audits",
        sa.Column("operator_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_operation_audits_operator_id_vendor_operators",
        "operation_audits",
        "vendor_operators",
        ["operator_id"],
        ["id"],
    )
    op.alter_column("operation_audits", "person_id", nullable=True)
    op.alter_column("operation_audits", "account_id", nullable=True)
    op.create_check_constraint(
        "ck_operation_audits_audit_actor",
        "operation_audits",
        "((operator_id IS NOT NULL AND account_id IS NULL AND person_id IS NULL) OR (operator_id IS NULL AND account_id IS NOT NULL AND person_id IS NOT NULL))",
    )

    # 4. local_sessions: local_credentials への外部キーを削除（運営者セッションも同居可能にするため）
    op.drop_constraint(
        "fk_local_sessions_subject_local_credentials",
        "local_sessions",
        type_="foreignkey",
    )

    # 5. local_credentials: corporate_id, email による法人スコープ化
    op.execute("DELETE FROM local_sessions")
    op.execute("DELETE FROM local_credentials")
    op.drop_constraint("pk_local_credentials", "local_credentials", type_="primary")
    op.drop_column("local_credentials", "login_id")
    op.add_column(
        "local_credentials",
        sa.Column("corporate_id", postgresql.UUID(as_uuid=True), nullable=False),
    )
    op.create_foreign_key(
        "fk_local_credentials_corporate_id_corporates",
        "local_credentials",
        "corporates",
        ["corporate_id"],
        ["id"],
    )
    op.add_column(
        "local_credentials",
        sa.Column("email", sa.String(255), nullable=False),
    )
    op.create_primary_key(
        "pk_local_credentials",
        "local_credentials",
        ["corporate_id", "email"],
    )


def downgrade() -> None:
    op.drop_table("vendor_operators")
