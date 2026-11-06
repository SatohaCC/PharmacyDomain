"""ログイン識別子と任意の連絡先メールを分離する。"""

import re

import sqlalchemy as sa
from alembic import op

revision: str = "20261102_0017"
down_revision: str | None = "20261031_0016"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    connection = op.get_bind()
    config = op.get_context().config
    mapping = op.get_context().opts.get("login_id_mapping")
    if mapping is None:
        mapping = (
            config.attributes.get("login_id_mapping", {}) if config is not None else {}
        )
    rows = (
        list(mapping)
        if op.get_context().as_sql
        else list(
            connection.execute(
                sa.text(
                    "SELECT 'vendor:' || id::text AS key FROM vendor_operators "
                    "UNION ALL SELECT corporate_id::text || ':' || email AS key FROM local_credentials"
                )
            ).scalars()
        )
    )
    if any(key not in mapping for key in rows):
        raise RuntimeError("既存の全資格情報に対するログインID対応表が必要です。")
    normalized: dict[str, str] = {}
    for key in rows:
        value = str(mapping[key]).strip().lower()
        if re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,63}", value) is None:
            raise RuntimeError("ログインID対応表に形式が不正な値があります。")
        normalized[key] = value
    scopes: set[tuple[str, str]] = set()
    for key, value in normalized.items():
        scope = "vendor" if key.startswith("vendor:") else key.split(":", 1)[0]
        if (scope, value) in scopes:
            raise RuntimeError("ログインID対応表に正規化後の重複があります。")
        scopes.add((scope, value))
    for table in ("vendor_operators", "local_credentials"):
        op.add_column(table, sa.Column("login_id", sa.String(64), nullable=True))
    for key, value in normalized.items():
        if key.startswith("vendor:"):
            connection.execute(
                sa.text(
                    "UPDATE vendor_operators SET login_id=:value WHERE id=CAST(:id AS uuid)"
                ),
                {"value": value, "id": key.removeprefix("vendor:")},
            )
        else:
            corporate_id, email = key.split(":", 1)
            connection.execute(
                sa.text(
                    "UPDATE local_credentials SET login_id=:value "
                    "WHERE corporate_id=CAST(:corporate_id AS uuid) AND email=:email"
                ),
                {"value": value, "corporate_id": corporate_id, "email": email},
            )
    op.drop_constraint("uq_vendor_operators_email", "vendor_operators", type_="unique")
    op.create_unique_constraint(
        "uq_vendor_operators_login_id", "vendor_operators", ["login_id"]
    )
    op.drop_constraint("pk_local_credentials", "local_credentials", type_="primary")
    op.create_primary_key(
        "pk_local_credentials", "local_credentials", ["corporate_id", "login_id"]
    )
    for table in ("vendor_operators", "local_credentials"):
        op.alter_column(table, "login_id", existing_type=sa.String(64), nullable=False)
        op.alter_column(table, "email", existing_type=sa.String(255), nullable=True)
    connection.execute(sa.text("DELETE FROM local_sessions"))


def downgrade() -> None:
    raise RuntimeError(
        "任意メールを必須識別子へ戻すと資格情報を失うため、自動巻戻しはできません。"
    )
