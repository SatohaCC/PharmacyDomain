"""identity各集約（本人・アカウント）へのcorporate_id必須化と法人整合制約の強化。"""

import sqlalchemy as sa
from alembic import op

revision: str = "20261031_0014"
down_revision: str | None = "20261030_0013"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # 1. account_people: corporate_id 列を追加し、corporates との FK および (id, corporate_id) 一意制約を追加
    op.add_column(
        "account_people",
        sa.Column(
            "corporate_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False
        ),
    )
    op.create_foreign_key(
        "fk_account_people_corporate_id_corporates",
        "account_people",
        "corporates",
        ["corporate_id"],
        ["id"],
    )
    op.create_unique_constraint(
        "uq_account_people_id_corporate",
        "account_people",
        ["id", "corporate_id"],
    )

    # 2. user_accounts: corporate_id 列を追加し、corporates との FK を追加
    op.add_column(
        "user_accounts",
        sa.Column(
            "corporate_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False
        ),
    )
    op.create_foreign_key(
        "fk_user_accounts_corporate_id_corporates",
        "user_accounts",
        "corporates",
        ["corporate_id"],
        ["id"],
    )
    # 古い FK を削除し、account_people (person_id, corporate_id) への複合 FK を追加
    op.drop_constraint(
        "fk_user_accounts_person_id_account_people", "user_accounts", type_="foreignkey"
    )
    op.create_foreign_key(
        "fk_user_accounts_person_corporate",
        "user_accounts",
        "account_people",
        ["person_id", "corporate_id"],
        ["id", "corporate_id"],
    )
    # 古い一意制約を削除（local_credentials からの FK 依存を先に解除）
    op.drop_constraint(
        "fk_local_credentials_subject_user_accounts",
        "local_credentials",
        type_="foreignkey",
    )
    op.drop_constraint("uq_user_accounts_person_id", "user_accounts", type_="unique")
    op.drop_constraint(
        "uq_user_accounts_external_subject", "user_accounts", type_="unique"
    )
    # 法人スコープの一意制約を追加
    op.create_unique_constraint(
        "uq_user_accounts_person_id",
        "user_accounts",
        ["corporate_id", "person_id"],
    )
    op.create_unique_constraint(
        "uq_user_accounts_external_subject",
        "user_accounts",
        ["corporate_id", "external_subject"],
    )
    op.create_unique_constraint(
        "uq_user_accounts_id_corporate",
        "user_accounts",
        ["id", "corporate_id"],
    )
    op.create_unique_constraint(
        "uq_user_accounts_id_corporate_person",
        "user_accounts",
        ["id", "corporate_id", "person_id"],
    )

    # 3. staff_person_links:
    op.drop_constraint(
        "fk_staff_person_links_person_id_account_people",
        "staff_person_links",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_staff_person_links_person_corporate",
        "staff_person_links",
        "account_people",
        ["person_id", "corporate_id"],
        ["id", "corporate_id"],
    )
    op.create_unique_constraint(
        "uq_staff_person_links_id_person_corporate",
        "staff_person_links",
        ["id", "person_id", "corporate_id"],
    )

    # 4. corporate_memberships:
    op.drop_constraint(
        "fk_corporate_memberships_account_id_user_accounts",
        "corporate_memberships",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_membership_account_corporate",
        "corporate_memberships",
        "user_accounts",
        ["account_id", "corporate_id"],
        ["id", "corporate_id"],
    )

    # 5. store_manager_assignments:
    op.drop_constraint(
        "fk_store_manager_assignments_staff_person",
        "store_manager_assignments",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_store_manager_assignments_staff_person",
        "store_manager_assignments",
        "staff_person_links",
        ["staff_id", "person_id", "corporate_id"],
        ["id", "person_id", "corporate_id"],
    )
    op.drop_constraint("ex_manager_person_period", "store_manager_assignments")
    op.execute(
        "ALTER TABLE store_manager_assignments ADD CONSTRAINT ex_manager_person_period "
        "EXCLUDE USING gist (corporate_id WITH =, person_id WITH =, period WITH &&) WHERE (status = 'confirmed')"
    )

    # 6. operation_audits:
    op.drop_constraint(
        "fk_audit_account_person", "operation_audits", type_="foreignkey"
    )
    op.create_foreign_key(
        "fk_audit_account_person",
        "operation_audits",
        "user_accounts",
        ["account_id", "corporate_id", "person_id"],
        ["id", "corporate_id", "person_id"],
    )

    # 7. ルーチンの更新（トリガ関数）
    op.execute("""CREATE OR REPLACE FUNCTION prevent_account_person_change() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        IF NEW.person_id IS DISTINCT FROM OLD.person_id OR NEW.corporate_id IS DISTINCT FROM OLD.corporate_id OR (OLD.external_subject IS NOT NULL AND NEW.external_subject IS DISTINCT FROM OLD.external_subject) THEN
            RAISE EXCEPTION 'アカウントの本人参照・法人・外部主体は変更できません。' USING ERRCODE = '23514', CONSTRAINT = 'ck_user_accounts_person_immutable';
        END IF;
        RETURN NEW;
    END;
    $$""")

    op.execute("""CREATE OR REPLACE FUNCTION check_membership_person() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        IF TG_OP = 'UPDATE' AND (NEW.account_id IS DISTINCT FROM OLD.account_id OR NEW.corporate_id IS DISTINCT FROM OLD.corporate_id) THEN
            RAISE EXCEPTION 'アクセス権の本人と法人は変更できません。' USING ERRCODE = '23514', CONSTRAINT = 'ck_membership_identity_immutable';
        END IF;
        IF NEW.staff_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM staff_person_links s JOIN user_accounts a ON a.person_id = s.person_id AND a.corporate_id = s.corporate_id
            WHERE s.id = NEW.staff_id AND s.corporate_id = NEW.corporate_id AND a.id = NEW.account_id
        ) THEN
            RAISE EXCEPTION 'スタッフと本人の対応が一致しません。' USING ERRCODE = '23514', CONSTRAINT = 'ck_membership_person';
        END IF;
        RETURN NEW;
    END;
    $$""")


def downgrade() -> None:
    pass
