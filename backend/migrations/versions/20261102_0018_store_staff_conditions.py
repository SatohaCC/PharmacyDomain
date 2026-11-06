"""法人共通の店舗ロールを明示的な店舗別ロールへ移す。"""

import sqlalchemy as sa
from alembic import op

revision: str = "20261102_0018"
down_revision: str | None = "20261102_0017"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        sa.text("""
        UPDATE corporate_memberships SET
          payload = (payload - 'store_ids') || jsonb_build_object(
            'role', CASE WHEN role = 'corporate_admin' THEN 'corporate_admin' ELSE 'member' END,
            'store_roles', COALESCE(payload->'store_roles', (SELECT jsonb_agg(jsonb_build_object(
                'store_id', store_id,
                'role', CASE WHEN corporate_memberships.role = 'store_viewer'
                         THEN 'store_viewer' ELSE 'store_operator' END))
              FROM jsonb_array_elements_text(COALESCE(payload->'store_ids', '[]'::jsonb)) AS ids(store_id)), '[]'::jsonb)),
          role = CASE WHEN role = 'corporate_admin' THEN 'corporate_admin' ELSE 'member' END
    """)
    )
    # 店舗別の週時間数は元データがないため、履歴を捏造せず未登録とする。
    op.execute(
        sa.text(
            "UPDATE staff_members SET payload = payload || '{\"work_conditions\": []}'::jsonb "
            "WHERE NOT (payload ? 'work_conditions')"
        )
    )


def downgrade() -> None:
    raise RuntimeError("店舗別ロール・勤務条件履歴を失うため、自動巻戻しはできません。")
