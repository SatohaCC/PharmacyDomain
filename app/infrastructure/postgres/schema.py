"""PostgreSQL のテーブル定義。"""

from __future__ import annotations

from typing import Final

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import DATERANGE, JSONB, UUID, ExcludeConstraint

metadata = MetaData(
    naming_convention={
        "ix": "ix_%(table_name)s_%(column_0_name)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
)


account_people = Table(
    "account_people",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
    Column("payload", JSONB, nullable=False),
    Column("version", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

user_accounts = Table(
    "user_accounts",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
    Column(
        "person_id", UUID(as_uuid=True), ForeignKey("account_people.id"), nullable=False
    ),
    Column("status", String(32), nullable=False),
    Column("external_subject", String(1000), nullable=True),
    Column("payload", JSONB, nullable=False),
    Column("version", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("person_id", name="uq_user_accounts_person_id"),
    UniqueConstraint("external_subject", name="uq_user_accounts_external_subject"),
    UniqueConstraint("id", "person_id", name="uq_user_accounts_id_person"),
)

staff_person_links = Table(
    "staff_person_links",
    metadata,
    Column(
        "id",
        UUID(as_uuid=True),
        ForeignKey("staff_members.id"),
        primary_key=True,
        nullable=False,
    ),
    Column(
        "corporate_id", UUID(as_uuid=True), ForeignKey("corporates.id"), nullable=False
    ),
    Column(
        "person_id", UUID(as_uuid=True), ForeignKey("account_people.id"), nullable=False
    ),
    Column("payload", JSONB, nullable=False),
    Column("version", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

corporate_memberships = Table(
    "corporate_memberships",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
    Column(
        "corporate_id", UUID(as_uuid=True), ForeignKey("corporates.id"), nullable=False
    ),
    Column(
        "account_id", UUID(as_uuid=True), ForeignKey("user_accounts.id"), nullable=False
    ),
    Column(
        "staff_id",
        UUID(as_uuid=True),
        ForeignKey("staff_person_links.id"),
        nullable=True,
    ),
    Column("role", String(32), nullable=False),
    Column("status", String(32), nullable=False),
    Column("payload", JSONB, nullable=False),
    Column("version", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint(
        "account_id", "corporate_id", name="uq_membership_account_corporate"
    ),
)
Index(
    "uq_membership_active_account",
    corporate_memberships.c.account_id,
    unique=True,
    postgresql_where=corporate_memberships.c.status == "active",
)

user_invitations = Table(
    "user_invitations",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
    Column(
        "person_id", UUID(as_uuid=True), ForeignKey("account_people.id"), nullable=False
    ),
    Column(
        "corporate_id", UUID(as_uuid=True), ForeignKey("corporates.id"), nullable=False
    ),
    Column("secret_digest", String(64), nullable=False),
    Column("status", String(32), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("payload", JSONB, nullable=False),
    Column("version", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("secret_digest", name="uq_user_invitations_digest"),
)

store_manager_assignments = Table(
    "store_manager_assignments",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
    Column(
        "corporate_id", UUID(as_uuid=True), ForeignKey("corporates.id"), nullable=False
    ),
    Column("store_id", UUID(as_uuid=True), ForeignKey("stores.id"), nullable=False),
    Column(
        "staff_id", UUID(as_uuid=True), ForeignKey("staff_members.id"), nullable=False
    ),
    Column("period", DATERANGE, nullable=False),
    Column("status", String(32), nullable=False),
    Column("payload", JSONB, nullable=False),
    Column("version", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    ExcludeConstraint(
        ("store_id", "="),
        ("period", "&&"),
        where=text("status = 'confirmed'"),
        name="ex_manager_store_period",
        using="gist",
    ),
    ExcludeConstraint(
        ("staff_id", "="),
        ("period", "&&"),
        where=text("status = 'confirmed'"),
        name="ex_manager_staff_period",
        using="gist",
    ),
)

#: 集約ではないテーブル。payload と version を持たない。
#: 増やすときは tests/infrastructure/postgres の表と揃える。
NON_AGGREGATE_TABLES = frozenset({"patient_number_sequences", "operation_audits"})

# 集約は payload（JSONB）を正とし、検索・一意性制約に要る値だけを列へ複製する。
# version は楽観ロック用で、集約ではなく行の世代を表す。
corporates = Table(
    "corporates",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
    Column("name", String(200), nullable=False),
    Column("representative_name", String(200), nullable=False),
    Column("status", String(32), nullable=False),
    Column("payload", JSONB, nullable=False),
    Column("version", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("name", name="uq_corporates_name"),
)

prescriptions = Table(
    "prescriptions",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
    Column("corporate_id", UUID(as_uuid=True), nullable=False),
    Column("store_id", UUID(as_uuid=True), nullable=False),
    Column("patient_id", UUID(as_uuid=True), nullable=False),
    Column("source_type", String(32), nullable=False),
    Column("document_number", String(36), nullable=False),
    Column("status", String(32), nullable=False),
    Column("payload", JSONB, nullable=False),
    Column("version", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

Index(
    "uq_prescriptions_electronic_document_number",
    prescriptions.c.corporate_id,
    prescriptions.c.document_number,
    unique=True,
    postgresql_where=prescriptions.c.source_type == "electronic",
)
Index(
    "ix_prescriptions_corporate_patient",
    prescriptions.c.corporate_id,
    prescriptions.c.patient_id,
)

dispensing_processes = Table(
    "dispensing_processes",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
    Column("corporate_id", UUID(as_uuid=True), nullable=False),
    Column("store_id", UUID(as_uuid=True), nullable=False),
    Column("patient_id", UUID(as_uuid=True), nullable=False),
    Column("prescription_id", UUID(as_uuid=True), nullable=False),
    Column("iteration", Integer, nullable=False),
    Column("status", String(32), nullable=False),
    Column("payload", JSONB, nullable=False),
    Column("version", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint(
        "corporate_id",
        "prescription_id",
        "iteration",
        name="uq_dispensing_processes_prescription_iteration",
    ),
    Index(
        "ix_dispensing_processes_corporate_prescription",
        "corporate_id",
        "prescription_id",
    ),
)

# --------------------------------------------------------------------------
# 法人配下のマスタ
# --------------------------------------------------------------------------

# Store / Staff の Repository契約は corporate_id への外部キーを明示的に要求する。
# 他のテーブルは契約に記述が無いので張らない。
stores = Table(
    "stores",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
    Column(
        "corporate_id",
        UUID(as_uuid=True),
        ForeignKey("corporates.id", name="fk_stores_corporate_id_corporates"),
        nullable=False,
    ),
    Column("name", String(200), nullable=False),
    Column("code", String(64), nullable=True),
    Column("insurance_pharmacy_number", String(32), nullable=True),
    Column("payload", JSONB, nullable=False),
    Column("version", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("corporate_id", "name", name="uq_stores_corporate_name"),
    Index("ix_stores_corporate_id", "corporate_id"),
)

# 店舗コードと保険薬局指定番号は任意項目。未設定どうしを衝突させないよう、
# NULL を除いた部分一意インデックスにする。
Index(
    "uq_stores_corporate_code",
    stores.c.corporate_id,
    stores.c.code,
    unique=True,
    postgresql_where=stores.c.code.isnot(None),
)
Index(
    "uq_stores_insurance_pharmacy_number",
    stores.c.insurance_pharmacy_number,
    unique=True,
    postgresql_where=stores.c.insurance_pharmacy_number.isnot(None),
)

staff_members = Table(
    "staff_members",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
    Column(
        "corporate_id",
        UUID(as_uuid=True),
        ForeignKey("corporates.id", name="fk_staff_members_corporate_id_corporates"),
        nullable=False,
    ),
    Column("code", String(64), nullable=True),
    Column("is_active", Boolean, nullable=False),
    Column("payload", JSONB, nullable=False),
    Column("version", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Index("ix_staff_members_corporate_id", "corporate_id"),
)

# スタッフコードは無効化後も再利用させない（過去の調剤録・監査の追跡を壊さない）。
# したがって is_active では絞らない。外部IDとは逆の判断であることに注意。
Index(
    "uq_staff_members_corporate_code",
    staff_members.c.corporate_id,
    staff_members.c.code,
    unique=True,
    postgresql_where=staff_members.c.code.isnot(None),
)

# --------------------------------------------------------------------------
# 患者
# --------------------------------------------------------------------------

patients = Table(
    "patients",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
    Column("corporate_id", UUID(as_uuid=True), nullable=False),
    Column("patient_number", Integer, nullable=False),
    Column("payload", JSONB, nullable=False),
    Column("version", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint(
        "corporate_id", "patient_number", name="uq_patients_corporate_number"
    ),
    Index("ix_patients_corporate_id", "corporate_id"),
)

# 患者番号の採番表。集約ではないので payload も version も持たない。
# 採番は1文（INSERT ... ON CONFLICT DO UPDATE ... RETURNING）で原子的に行う。
patient_number_sequences = Table(
    "patient_number_sequences",
    metadata,
    Column("corporate_id", UUID(as_uuid=True), primary_key=True, nullable=False),
    Column("last_number", Integer, nullable=False),
)

patient_external_identifiers = Table(
    "patient_external_identifiers",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
    Column("corporate_id", UUID(as_uuid=True), nullable=False),
    Column("patient_id", UUID(as_uuid=True), nullable=False),
    Column("system_name", String(200), nullable=False),
    Column("external_patient_id", String(200), nullable=False),
    Column("is_active", Boolean, nullable=False),
    Column("payload", JSONB, nullable=False),
    Column("version", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Index(
        "ix_patient_external_identifiers_corporate_patient",
        "corporate_id",
        "patient_id",
    ),
)

# 一意とみなすのは有効な行だけ。誤った患者へ紐付けた外部IDを無効化してから
# 正しい患者へ付け替えられるようにするため、無効化済みは衝突扱いにしない。
Index(
    "uq_patient_external_identifiers_active_source",
    patient_external_identifiers.c.corporate_id,
    patient_external_identifiers.c.system_name,
    patient_external_identifiers.c.external_patient_id,
    unique=True,
    postgresql_where=patient_external_identifiers.c.is_active,
)

# --------------------------------------------------------------------------
# 資格と受付
# --------------------------------------------------------------------------

patient_coverages = Table(
    "patient_coverages",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
    Column("corporate_id", UUID(as_uuid=True), nullable=False),
    Column("patient_id", UUID(as_uuid=True), nullable=False),
    Column("coverage_type", String(32), nullable=False),
    Column("priority", Integer, nullable=False),
    # 制度期間と有効化区間の交差。実効期間が空（無効化済みなど）なら NULL にし、
    # 競合判定の対象から外す。両端を含む閉区間なので境界は '[]' で入れる。
    Column("effective_range", DATERANGE, nullable=True),
    Column("payload", JSONB, nullable=False),
    Column("version", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    # 同一法人・患者・制度・順位で実効期間が1日でも重なる行を拒否する。
    # 「期間の重なり」は一意制約では表せないので排他制約を使う。
    ExcludeConstraint(
        ("corporate_id", "="),
        ("patient_id", "="),
        ("coverage_type", "="),
        ("priority", "="),
        ("effective_range", "&&"),
        name="excl_patient_coverages_effective_period",
        using="gist",
        where=text("effective_range IS NOT NULL"),
    ),
    Index("ix_patient_coverages_corporate_patient", "corporate_id", "patient_id"),
)

coverage_selection_records = Table(
    "coverage_selection_records",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
    Column("corporate_id", UUID(as_uuid=True), nullable=False),
    Column("store_id", UUID(as_uuid=True), nullable=False),
    Column("patient_id", UUID(as_uuid=True), nullable=False),
    Column("applied_on", Date, nullable=False),
    Column("recorded_at", DateTime(timezone=True), nullable=False),
    Column("payload", JSONB, nullable=False),
    Column("version", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    # 履歴なので一意性は課さない。最新1件の取得だけが速ければよい。
    Index(
        "ix_coverage_selection_records_latest",
        "corporate_id",
        "store_id",
        "patient_id",
        "recorded_at",
        "id",
    ),
)

# --------------------------------------------------------------------------
# 薬歴
# --------------------------------------------------------------------------

medication_history_records = Table(
    "medication_history_records",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
    Column("corporate_id", UUID(as_uuid=True), nullable=False),
    Column("store_id", UUID(as_uuid=True), nullable=False),
    Column("patient_id", UUID(as_uuid=True), nullable=False),
    Column("dispensing_id", UUID(as_uuid=True), nullable=False),
    Column("prescription_id", UUID(as_uuid=True), nullable=False),
    Column("status", String(32), nullable=False),
    Column("counseled_at", DateTime(timezone=True), nullable=False),
    Column("payload", JSONB, nullable=False),
    Column("version", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Index(
        "ix_medication_history_records_corporate_patient",
        "corporate_id",
        "patient_id",
        "counseled_at",
    ),
)

# 確定済だけを1件に制限する。下書きは書きかけを複数持つのが正当なので対象外。
Index(
    "uq_medication_history_records_finalized_dispensing",
    medication_history_records.c.corporate_id,
    medication_history_records.c.dispensing_id,
    unique=True,
    postgresql_where=medication_history_records.c.status == "finalized",
)

patient_medical_profiles = Table(
    "patient_medical_profiles",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
    Column("corporate_id", UUID(as_uuid=True), nullable=False),
    Column("patient_id", UUID(as_uuid=True), nullable=False),
    Column("payload", JSONB, nullable=False),
    Column("version", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    # 患者との1:1は id ではなく patient_id の一意制約で表す。
    UniqueConstraint(
        "corporate_id", "patient_id", name="uq_patient_medical_profiles_patient"
    ),
)

# --------------------------------------------------------------------------
# 医薬品マスタ（非テナント）
# --------------------------------------------------------------------------

# 薬価基準は国が定めるので法人ごとに内容が違わない。corporate_id を持たせない。
medicines = Table(
    "medicines",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
    # MedicineIdentifier は (code_type, code) の組で code は NULL を取りうる。
    # 排他制約の `=` は NULL 同士を等しいと扱わないため、ドメインの等価性と
    # 一致する非NULLのキー文字列を別に持つ。
    Column("identifier_key", String(80), nullable=False),
    Column("code_type", String(32), nullable=False),
    Column("code", String(64), nullable=True),
    Column("listed_on", Date, nullable=False),
    Column("withdrawn_on", Date, nullable=True),
    Column("effective_range", DATERANGE, nullable=False),
    Column("payload", JSONB, nullable=False),
    Column("version", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    # 同じ薬品コードで期間が重なると、ある日付で引いたときに2行返り
    # 「その日のマスタ」が一意に定まらなくなる。
    ExcludeConstraint(
        ("identifier_key", "="),
        ("effective_range", "&&"),
        name="excl_medicines_effective_period",
        using="gist",
    ),
    Index("ix_medicines_identifier_listed_on", "identifier_key", "listed_on"),
)


operation_audits = Table(
    "operation_audits",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
    Column("person_id", UUID(as_uuid=True), nullable=False),
    Column("account_id", UUID(as_uuid=True), nullable=False),
    Column("operation", String(150), nullable=False),
    Column("resource_id", UUID(as_uuid=True), nullable=False),
    Column("corporate_id", UUID(as_uuid=True), nullable=True),
    Column("store_id", UUID(as_uuid=True), nullable=True),
    Column("recorded_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["account_id", "person_id"],
        ["user_accounts.id", "user_accounts.person_id"],
        name="fk_audit_account_person",
    ),
)


#: テーブル定義では表せない、関数とトリガによる保護。
#:
#: 「アカウントの本人参照は変えられない」「アクセス権のスタッフは本人と一致する」
#: といった規則は、列の制約でも一意索引でも表せない。マイグレーションだけが
#: 知っている状態にすると、スキーマ定義との突き合わせから外れ、名前を変えても
#: Repository側の制約名との対応が切れたことに誰も気づけない。
#: マイグレーションが出すDDLと**同じ文字列**をここに置き、
#: ``tests/infrastructure/postgres/test_schema_migration_consistency.py`` が
#: 両者の一致を検査する。
SCHEMA_ROUTINES: Final[tuple[str, ...]] = (
    """CREATE OR REPLACE FUNCTION prevent_account_person_change() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        IF NEW.person_id IS DISTINCT FROM OLD.person_id THEN
            RAISE EXCEPTION 'アカウントの本人参照は変更できません。' USING ERRCODE = '23514', CONSTRAINT = 'ck_user_accounts_person_immutable';
        END IF;
        RETURN NEW;
    END;
    $$""",
    "CREATE TRIGGER user_accounts_person_immutable BEFORE UPDATE ON user_accounts FOR EACH ROW EXECUTE FUNCTION prevent_account_person_change()",
    """CREATE OR REPLACE FUNCTION check_staff_person_link() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        IF TG_OP = 'UPDATE' AND (NEW.person_id IS DISTINCT FROM OLD.person_id OR NEW.corporate_id IS DISTINCT FROM OLD.corporate_id) THEN
            RAISE EXCEPTION '本人対応は変更できません。' USING ERRCODE = '23514', CONSTRAINT = 'ck_staff_person_immutable';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM staff_members WHERE id = NEW.id AND corporate_id = NEW.corporate_id) THEN
            RAISE EXCEPTION 'スタッフの法人が一致しません。' USING ERRCODE = '23514', CONSTRAINT = 'ck_staff_person_corporate';
        END IF;
        RETURN NEW;
    END;
    $$""",
    "CREATE TRIGGER staff_person_link_guard BEFORE INSERT OR UPDATE ON staff_person_links FOR EACH ROW EXECUTE FUNCTION check_staff_person_link()",
    """CREATE OR REPLACE FUNCTION check_membership_person() RETURNS trigger LANGUAGE plpgsql AS $$
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
    $$""",
    "CREATE TRIGGER membership_person_guard BEFORE INSERT OR UPDATE ON corporate_memberships FOR EACH ROW EXECUTE FUNCTION check_membership_person()",
    """CREATE OR REPLACE FUNCTION prevent_audit_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        RAISE EXCEPTION '操作監査は追記専用です。' USING ERRCODE = '23514', CONSTRAINT = 'ck_operation_audit_immutable';
    END;
    $$""",
    "CREATE TRIGGER operation_audit_immutable BEFORE UPDATE OR DELETE ON operation_audits FOR EACH ROW EXECUTE FUNCTION prevent_audit_mutation()",
)
