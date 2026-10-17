"""本人・アクセス権・管理薬剤師の永続化と旧店舗payloadの移行。

管理薬剤師の任命に本人の列と人単位の排他制約を足すとき、``ALTER TABLE`` を後続の
版で足すのではなく、この版の ``CREATE TABLE`` を直した。突き合わせの検査は、
マイグレーションが出す ``CREATE TABLE`` の集合と、スキーマ定義から生成した
``CREATE TABLE`` の集合を比べる。後続版で ``ALTER`` すると、この版が作る古い形が
集合に残り続けて永久に一致しない。適用済みの環境はスキーマを作り直すこと。
"""

from alembic import op

revision = "20260917_0003"
down_revision = "20260829_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """新しい管理データを作り、本人参照をDBでも固定する。"""
    op.execute(
        "CREATE TABLE account_people (\n\tid UUID NOT NULL, \n\tpayload JSONB NOT NULL, \n\tversion INTEGER NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tCONSTRAINT pk_account_people PRIMARY KEY (id)\n)"
    )
    op.execute(
        "CREATE TABLE user_accounts (\n\tid UUID NOT NULL, \n\tperson_id UUID NOT NULL, \n\tstatus VARCHAR(32) NOT NULL, \n\texternal_subject VARCHAR(1000), \n\tpayload JSONB NOT NULL, \n\tversion INTEGER NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tCONSTRAINT pk_user_accounts PRIMARY KEY (id), \n\tCONSTRAINT uq_user_accounts_person_id UNIQUE (person_id), \n\tCONSTRAINT uq_user_accounts_external_subject UNIQUE (external_subject), \n\tCONSTRAINT uq_user_accounts_id_person UNIQUE (id, person_id), \n\tCONSTRAINT fk_user_accounts_person_id_account_people FOREIGN KEY(person_id) REFERENCES account_people (id)\n)"
    )
    op.execute(
        "CREATE TABLE user_invitations (\n\tid UUID NOT NULL, \n\tperson_id UUID NOT NULL, \n\tcorporate_id UUID NOT NULL, \n\tsecret_digest VARCHAR(64) NOT NULL, \n\tstatus VARCHAR(32) NOT NULL, \n\texpires_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tpayload JSONB NOT NULL, \n\tversion INTEGER NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tCONSTRAINT pk_user_invitations PRIMARY KEY (id), \n\tCONSTRAINT uq_user_invitations_digest UNIQUE (secret_digest), \n\tCONSTRAINT fk_user_invitations_person_id_account_people FOREIGN KEY(person_id) REFERENCES account_people (id), \n\tCONSTRAINT fk_user_invitations_corporate_id_corporates FOREIGN KEY(corporate_id) REFERENCES corporates (id)\n)"
    )
    op.execute(
        "CREATE TABLE staff_person_links (\n\tid UUID NOT NULL, \n\tcorporate_id UUID NOT NULL, \n\tperson_id UUID NOT NULL, \n\tpayload JSONB NOT NULL, \n\tversion INTEGER NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tCONSTRAINT pk_staff_person_links PRIMARY KEY (id), \n\tCONSTRAINT uq_staff_person_links_id_person UNIQUE (id, person_id), \n\tCONSTRAINT fk_staff_person_links_id_staff_members FOREIGN KEY(id) REFERENCES staff_members (id), \n\tCONSTRAINT fk_staff_person_links_corporate_id_corporates FOREIGN KEY(corporate_id) REFERENCES corporates (id), \n\tCONSTRAINT fk_staff_person_links_person_id_account_people FOREIGN KEY(person_id) REFERENCES account_people (id)\n)"
    )
    op.execute(
        "CREATE TABLE store_manager_assignments (\n\tid UUID NOT NULL, \n\tcorporate_id UUID NOT NULL, \n\tstore_id UUID NOT NULL, \n\tstaff_id UUID NOT NULL, \n\tperson_id UUID NOT NULL, \n\tperiod DATERANGE NOT NULL, \n\tstatus VARCHAR(32) NOT NULL, \n\tpayload JSONB NOT NULL, \n\tversion INTEGER NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tCONSTRAINT pk_store_manager_assignments PRIMARY KEY (id), \n\tCONSTRAINT fk_store_manager_assignments_staff_person FOREIGN KEY(staff_id, person_id) REFERENCES staff_person_links (id, person_id), \n\tCONSTRAINT ex_manager_store_period EXCLUDE USING gist (store_id WITH =, period WITH &&) WHERE (status = 'confirmed'), \n\tCONSTRAINT ex_manager_person_period EXCLUDE USING gist (person_id WITH =, period WITH &&) WHERE (status = 'confirmed'), \n\tCONSTRAINT fk_store_manager_assignments_corporate_id_corporates FOREIGN KEY(corporate_id) REFERENCES corporates (id), \n\tCONSTRAINT fk_store_manager_assignments_store_id_stores FOREIGN KEY(store_id) REFERENCES stores (id)\n)"
    )
    op.execute(
        "CREATE TABLE corporate_memberships (\n\tid UUID NOT NULL, \n\tcorporate_id UUID NOT NULL, \n\taccount_id UUID NOT NULL, \n\tstaff_id UUID, \n\trole VARCHAR(32) NOT NULL, \n\tstatus VARCHAR(32) NOT NULL, \n\tpayload JSONB NOT NULL, \n\tversion INTEGER NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tCONSTRAINT pk_corporate_memberships PRIMARY KEY (id), \n\tCONSTRAINT uq_membership_account_corporate UNIQUE (account_id, corporate_id), \n\tCONSTRAINT fk_corporate_memberships_corporate_id_corporates FOREIGN KEY(corporate_id) REFERENCES corporates (id), \n\tCONSTRAINT fk_corporate_memberships_account_id_user_accounts FOREIGN KEY(account_id) REFERENCES user_accounts (id), \n\tCONSTRAINT fk_corporate_memberships_staff_id_staff_person_links FOREIGN KEY(staff_id) REFERENCES staff_person_links (id)\n)"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_membership_active_account ON corporate_memberships (account_id) WHERE status = 'active'"
    )
    op.execute(
        'UPDATE stores SET payload = payload || \'{"status": "active", "status_history": []}\'::jsonb WHERE NOT (payload ? \'status\')'
    )
    op.execute("""CREATE OR REPLACE FUNCTION prevent_account_person_change() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        IF NEW.person_id IS DISTINCT FROM OLD.person_id THEN
            RAISE EXCEPTION 'アカウントの本人参照は変更できません。' USING ERRCODE = '23514', CONSTRAINT = 'ck_user_accounts_person_immutable';
        END IF;
        RETURN NEW;
    END;
    $$""")
    op.execute(
        "CREATE TRIGGER user_accounts_person_immutable BEFORE UPDATE ON user_accounts FOR EACH ROW EXECUTE FUNCTION prevent_account_person_change()"
    )
    op.execute("""CREATE OR REPLACE FUNCTION check_staff_person_link() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        IF TG_OP = 'UPDATE' AND (NEW.person_id IS DISTINCT FROM OLD.person_id OR NEW.corporate_id IS DISTINCT FROM OLD.corporate_id) THEN
            RAISE EXCEPTION '本人対応は変更できません。' USING ERRCODE = '23514', CONSTRAINT = 'ck_staff_person_immutable';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM staff_members WHERE id = NEW.id AND corporate_id = NEW.corporate_id) THEN
            RAISE EXCEPTION 'スタッフの法人が一致しません。' USING ERRCODE = '23514', CONSTRAINT = 'ck_staff_person_corporate';
        END IF;
        RETURN NEW;
    END;
    $$""")
    op.execute(
        "CREATE TRIGGER staff_person_link_guard BEFORE INSERT OR UPDATE ON staff_person_links FOR EACH ROW EXECUTE FUNCTION check_staff_person_link()"
    )
    op.execute("""CREATE OR REPLACE FUNCTION check_membership_person() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        IF TG_OP = 'UPDATE' AND (NEW.account_id IS DISTINCT FROM OLD.account_id OR NEW.corporate_id IS DISTINCT FROM OLD.corporate_id) THEN
            RAISE EXCEPTION 'アクセス権の本人と法人は変更できません。' USING ERRCODE = '23514', CONSTRAINT = 'ck_membership_identity_immutable';
        END IF;
        IF NEW.staff_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM staff_person_links s JOIN user_accounts a ON a.person_id = s.person_id
            WHERE s.id = NEW.staff_id AND s.corporate_id = NEW.corporate_id AND a.id = NEW.account_id
        ) THEN
            RAISE EXCEPTION 'スタッフと本人の対応が一致しません。' USING ERRCODE = '23514', CONSTRAINT = 'ck_membership_person';
        END IF;
        RETURN NEW;
    END;
    $$""")
    op.execute(
        "CREATE TRIGGER membership_person_guard BEFORE INSERT OR UPDATE ON corporate_memberships FOR EACH ROW EXECUTE FUNCTION check_membership_person()"
    )

    op.execute(
        "\nCREATE TABLE operation_audits (\n\tid UUID NOT NULL, \n\tperson_id UUID NOT NULL, \n\taccount_id UUID NOT NULL, \n\toperation VARCHAR(150) NOT NULL, \n\tresource_id UUID NOT NULL, \n\tcorporate_id UUID, \n\tstore_id UUID, \n\trecorded_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tCONSTRAINT pk_operation_audits PRIMARY KEY (id), \n\tCONSTRAINT fk_audit_account_person FOREIGN KEY(account_id, person_id) REFERENCES user_accounts (id, person_id)\n)\n\n"
    )

    op.execute("""CREATE OR REPLACE FUNCTION prevent_audit_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        RAISE EXCEPTION '操作監査は追記専用です。' USING ERRCODE = '23514', CONSTRAINT = 'ck_operation_audit_immutable';
    END;
    $$""")
    op.execute(
        "CREATE TRIGGER operation_audit_immutable BEFORE UPDATE OR DELETE ON operation_audits FOR EACH ROW EXECUTE FUNCTION prevent_audit_mutation()"
    )


def downgrade() -> None:
    """新テーブルを参照の逆順で削除する。"""
    op.drop_table("operation_audits")
    op.drop_table("corporate_memberships")
    op.drop_table("store_manager_assignments")
    op.drop_table("staff_person_links")
    op.drop_table("user_invitations")
    op.drop_table("user_accounts")
    op.drop_table("account_people")
    op.execute("DROP FUNCTION prevent_account_person_change()")
    op.execute("DROP FUNCTION check_staff_person_link()")
    op.execute("DROP FUNCTION check_membership_person()")

    op.execute("DROP FUNCTION prevent_audit_mutation()")
