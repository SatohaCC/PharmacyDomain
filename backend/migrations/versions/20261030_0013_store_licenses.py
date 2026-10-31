"""店舗の薬局開設許可および麻薬小売業者免許の検索列を追加する。"""

import sqlalchemy as sa
from alembic import op

revision: str = "20261030_0013"
down_revision: str | None = "20261018_0012"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """店舗テーブルに薬局開設許可および麻薬小売業者免許の検索列を追加する。"""
    op.add_column(
        "stores", sa.Column("pharmacy_license_number", sa.String(64), nullable=True)
    )
    op.add_column(
        "stores", sa.Column("pharmacy_license_valid_from", sa.Date(), nullable=True)
    )
    op.add_column(
        "stores", sa.Column("pharmacy_license_valid_to", sa.Date(), nullable=True)
    )
    op.add_column(
        "stores", sa.Column("narcotics_license_number", sa.String(64), nullable=True)
    )
    op.add_column(
        "stores", sa.Column("narcotics_license_valid_from", sa.Date(), nullable=True)
    )
    op.add_column(
        "stores", sa.Column("narcotics_license_valid_to", sa.Date(), nullable=True)
    )


def downgrade() -> None:
    """店舗テーブルから薬局開設許可および麻薬小売業者免許の検索列を削除する。"""
    op.drop_column("stores", "narcotics_license_valid_to")
    op.drop_column("stores", "narcotics_license_valid_from")
    op.drop_column("stores", "narcotics_license_number")
    op.drop_column("stores", "pharmacy_license_valid_to")
    op.drop_column("stores", "pharmacy_license_valid_from")
    op.drop_column("stores", "pharmacy_license_number")
