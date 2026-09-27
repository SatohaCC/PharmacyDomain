"""PostgreSQL のテーブル定義。"""

from __future__ import annotations

from typing import Final

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    PrimaryKeyConstraint,
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
    # 管理薬剤師の任命が「そのスタッフの本人」を写していることを、複合外部キーで
    # 参照できるようにする。参照される側には一意制約が要る。
    UniqueConstraint("id", "person_id", name="uq_staff_person_links_id_person"),
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
    Column("staff_id", UUID(as_uuid=True), nullable=False),
    Column("person_id", UUID(as_uuid=True), nullable=False),
    Column("period", DATERANGE, nullable=False),
    Column("status", String(32), nullable=False),
    Column("payload", JSONB, nullable=False),
    Column("version", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    # スタッフではなく「スタッフと本人の対応」を参照する。こうすると、対応の
    # 無いスタッフを任命できず、写した本人が対応とずれることもない。スタッフの
    # 実在は staff_person_links.id 側の外部キーが引き続き保証する。
    ForeignKeyConstraint(
        ["staff_id", "person_id"],
        ["staff_person_links.id", "staff_person_links.person_id"],
        name="fk_store_manager_assignments_staff_person",
    ),
    ExcludeConstraint(
        ("store_id", "="),
        ("period", "&&"),
        where=text("status = 'confirmed'"),
        name="ex_manager_store_period",
        using="gist",
    ),
    # スタッフ単位の排他制約は置かない。複合外部キーによりスタッフIDから本人は
    # 一意に決まるので、同一スタッフの重複は人単位の制約が必ず捕らえる。両方を
    # 置くと、同一スタッフの重複でどちらの制約が報告されるかがサーバ任せになり、
    # 業務例外の型が揺れる。
    # 専任義務は自然人にかかる。法人IDを鍵に含めてはならない（含めると、
    # グループ内の別法人どうしで同じ人物が兼務できてしまう）。
    ExcludeConstraint(
        ("person_id", "="),
        ("period", "&&"),
        where=text("status = 'confirmed'"),
        name="ex_manager_person_period",
        using="gist",
    ),
)

#: 集約ではないテーブル。payload と version を持たない。
#: 増やすときは tests/infrastructure/postgres の表と揃える。
NON_AGGREGATE_TABLES = frozenset(
    {
        "patient_number_sequences",
        "operation_audits",
        "medication_history_legacy_archives",
        "legacy_tracing_report_links",
    }
)

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
    Column("store_id", UUID(as_uuid=True), nullable=True),
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
    patient_external_identifiers.c.store_id,
    patient_external_identifiers.c.system_name,
    patient_external_identifiers.c.external_patient_id,
    unique=True,
    postgresql_where=text("is_active AND store_id IS NOT NULL"),
)
Index(
    "uq_patient_external_identifiers_active_legacy_source",
    patient_external_identifiers.c.corporate_id,
    patient_external_identifiers.c.system_name,
    patient_external_identifiers.c.external_patient_id,
    unique=True,
    postgresql_where=text("is_active AND store_id IS NULL"),
)

# --------------------------------------------------------------------------
# 資格と受付
# --------------------------------------------------------------------------

receptions = Table(
    "receptions",
    metadata,
    Column("id", UUID(as_uuid=True), nullable=False),
    Column("corporate_id", UUID(as_uuid=True), nullable=False),
    Column("store_id", UUID(as_uuid=True), nullable=False),
    Column("event_id", UUID(as_uuid=True), nullable=True),
    Column("payload", JSONB, nullable=False),
    Column("version", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    PrimaryKeyConstraint("corporate_id", "store_id", "id", name="pk_receptions"),
    Index("ix_receptions_corporate_store", "corporate_id", "store_id"),
)

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
# 業務Event
# --------------------------------------------------------------------------

event_definitions = Table(
    "event_definitions",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
    Column("corporate_id", UUID(as_uuid=True), nullable=True),
    Column("standard_code", String(80), nullable=True),
    Column("name", String(200), nullable=False),
    Column("is_active", Boolean, nullable=False),
    Column("payload", JSONB, nullable=False),
    Column("version", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint(
        "(corporate_id IS NULL AND standard_code IS NOT NULL) OR "
        "(corporate_id IS NOT NULL AND standard_code IS NULL)",
        name="standard_or_corporate",
    ),
    Index(
        "uq_event_definitions_standard_code",
        "standard_code",
        unique=True,
        postgresql_where=text("corporate_id IS NULL"),
    ),
    Index(
        "uq_event_definitions_corporate_active_name",
        "corporate_id",
        "name",
        unique=True,
        postgresql_where=text("corporate_id IS NOT NULL AND is_active"),
    ),
    UniqueConstraint("id", "corporate_id", name="uq_event_definitions_identity_scope"),
)

# Eventから処方箋・調剤の範囲を複合FKで照合する。
prescriptions.append_constraint(
    UniqueConstraint(
        "id",
        "corporate_id",
        "store_id",
        "patient_id",
        name="uq_prescriptions_scope_identity",
    )
)
dispensing_processes.append_constraint(
    UniqueConstraint(
        "id",
        "corporate_id",
        "store_id",
        "patient_id",
        "prescription_id",
        name="uq_dispensing_processes_event_identity",
    )
)

care_events = Table(
    "care_events",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
    Column("event_type_id", UUID(as_uuid=True), nullable=False),
    Column("event_definition_corporate_id", UUID(as_uuid=True), nullable=True),
    Column("event_type_standard_code", String(80), nullable=True),
    Column("event_type_name", String(200), nullable=False),
    Column("corporate_id", UUID(as_uuid=True), nullable=False),
    Column("store_id", UUID(as_uuid=True), nullable=False),
    Column("patient_id", UUID(as_uuid=True), nullable=False),
    Column("occurred_at", DateTime(timezone=True), nullable=True),
    Column("occurred_at_is_unknown", Boolean, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("related_event_id", UUID(as_uuid=True), nullable=True),
    Column("reception_id", UUID(as_uuid=True), nullable=True),
    Column("prescription_id", UUID(as_uuid=True), nullable=True),
    Column("dispensing_id", UUID(as_uuid=True), nullable=True),
    Column("payload", JSONB, nullable=False),
    Column("version", Integer, nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint(
        "id", "corporate_id", "patient_id", name="uq_care_events_scope_identity"
    ),
    UniqueConstraint(
        "id",
        "corporate_id",
        "store_id",
        "patient_id",
        name="uq_care_events_full_scope_identity",
    ),
    UniqueConstraint(
        "id",
        "corporate_id",
        "store_id",
        "patient_id",
        "prescription_id",
        "dispensing_id",
        name="uq_care_events_resource_identity",
    ),
    UniqueConstraint(
        "id",
        "corporate_id",
        "store_id",
        "reception_id",
        name="uq_care_events_reception_identity",
    ),
    ForeignKeyConstraint(
        ["event_type_id"],
        ["event_definitions.id"],
        name="fk_care_events_event_type",
    ),
    ForeignKeyConstraint(
        ["event_type_id", "event_definition_corporate_id"],
        ["event_definitions.id", "event_definitions.corporate_id"],
        name="fk_care_events_event_type_scope",
    ),
    ForeignKeyConstraint(
        ["related_event_id", "corporate_id", "patient_id"],
        ["care_events.id", "care_events.corporate_id", "care_events.patient_id"],
        name="fk_care_events_related_scope",
    ),
    ForeignKeyConstraint(
        ["corporate_id", "store_id", "reception_id"],
        ["receptions.corporate_id", "receptions.store_id", "receptions.id"],
        name="fk_care_events_reception_scope",
    ),
    ForeignKeyConstraint(
        ["prescription_id", "corporate_id", "store_id", "patient_id"],
        [
            "prescriptions.id",
            "prescriptions.corporate_id",
            "prescriptions.store_id",
            "prescriptions.patient_id",
        ],
        name="fk_care_events_prescription_scope",
    ),
    ForeignKeyConstraint(
        [
            "dispensing_id",
            "corporate_id",
            "store_id",
            "patient_id",
            "prescription_id",
        ],
        [
            "dispensing_processes.id",
            "dispensing_processes.corporate_id",
            "dispensing_processes.store_id",
            "dispensing_processes.patient_id",
            "dispensing_processes.prescription_id",
        ],
        name="fk_care_events_dispensing_scope",
    ),
    CheckConstraint(
        "(occurred_at IS NOT NULL AND NOT occurred_at_is_unknown) OR "
        "(occurred_at IS NULL AND occurred_at_is_unknown)",
        name="occurred_at_known_state",
    ),
    CheckConstraint(
        "event_definition_corporate_id IS NULL OR "
        "event_definition_corporate_id = corporate_id",
        name="event_type_corporate_scope",
    ),
    CheckConstraint(
        "related_event_id IS NULL OR related_event_id <> id", name="not_self_related"
    ),
    CheckConstraint(
        "dispensing_id IS NULL OR prescription_id IS NOT NULL",
        name="dispensing_requires_prescription",
    ),
    Index(
        "ix_care_events_corporate_store_patient_occurred_at",
        "corporate_id",
        "store_id",
        "patient_id",
        "occurred_at",
        "id",
    ),
    Index(
        "uq_care_events_reception",
        "corporate_id",
        "store_id",
        "reception_id",
        unique=True,
        postgresql_where=text("reception_id IS NOT NULL"),
    ),
)

receptions.append_constraint(
    ForeignKeyConstraint(
        ["event_id", "corporate_id", "store_id", "id"],
        [
            "care_events.id",
            "care_events.corporate_id",
            "care_events.store_id",
            "care_events.reception_id",
        ],
        name="fk_receptions_event_scope",
    )
)
receptions.append_constraint(UniqueConstraint("event_id", name="uq_receptions_event"))

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
    Column("event_id", UUID(as_uuid=True), nullable=False),
    Column("dispensing_id", UUID(as_uuid=True), nullable=True),
    Column("prescription_id", UUID(as_uuid=True), nullable=True),
    Column("status", String(32), nullable=False),
    Column("counseled_at", DateTime(timezone=True), nullable=True),
    Column("recorded_at", DateTime(timezone=True), nullable=True),
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
    ForeignKeyConstraint(
        [
            "event_id",
            "corporate_id",
            "store_id",
            "patient_id",
        ],
        [
            "care_events.id",
            "care_events.corporate_id",
            "care_events.store_id",
            "care_events.patient_id",
        ],
        name="fk_medication_history_records_event_scope",
    ),
    UniqueConstraint("event_id", name="uq_medication_history_records_event"),
    ForeignKeyConstraint(
        [
            "event_id",
            "corporate_id",
            "store_id",
            "patient_id",
            "prescription_id",
            "dispensing_id",
        ],
        [
            "care_events.id",
            "care_events.corporate_id",
            "care_events.store_id",
            "care_events.patient_id",
            "care_events.prescription_id",
            "care_events.dispensing_id",
        ],
        name="fk_medication_history_records_event_resources",
    ),
    ForeignKeyConstraint(
        [
            "dispensing_id",
            "corporate_id",
            "store_id",
            "patient_id",
            "prescription_id",
        ],
        [
            "dispensing_processes.id",
            "dispensing_processes.corporate_id",
            "dispensing_processes.store_id",
            "dispensing_processes.patient_id",
            "dispensing_processes.prescription_id",
        ],
        name="fk_medication_history_records_dispensing_scope",
    ),
    CheckConstraint(
        "dispensing_id IS NULL OR prescription_id IS NOT NULL",
        name="dispensing_requires_prescription",
    ),
)

# 旧FollowUpRecordと旧payloadを監査・API互換のために保管する移行アーカイブ。
# 現行薬歴の読み書き対象にはせず、migrationのみが追記する。
medication_history_legacy_archives = Table(
    "medication_history_legacy_archives",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
    Column("legacy_record_id", UUID(as_uuid=True), nullable=False),
    Column("legacy_parent_record_id", UUID(as_uuid=True), nullable=True),
    Column("corporate_id", UUID(as_uuid=True), nullable=False),
    Column("store_id", UUID(as_uuid=True), nullable=False),
    Column("patient_id", UUID(as_uuid=True), nullable=False),
    Column("event_id", UUID(as_uuid=True), nullable=False),
    Column("archive_kind", String(32), nullable=False),
    Column("original_payload", JSONB, nullable=False),
    Column("archived_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint(
        "legacy_record_id", name="uq_medication_history_legacy_archives_record"
    ),
    CheckConstraint(
        "(archive_kind = 'record' AND legacy_parent_record_id IS NULL) OR "
        "(archive_kind = 'follow_up' AND legacy_parent_record_id IS NOT NULL)",
        name="archive_kind_parent",
    ),
    ForeignKeyConstraint(
        ["event_id"],
        ["care_events.id"],
        name="fk_medication_history_legacy_archives_event",
    ),
)

legacy_tracing_report_links = Table(
    "legacy_tracing_report_links",
    metadata,
    Column("corporate_id", UUID(as_uuid=True), nullable=False),
    Column("legacy_parent_record_id", UUID(as_uuid=True), nullable=False),
    Column("legacy_tracing_report_id", UUID(as_uuid=True), nullable=False),
    Column("target_record_id", UUID(as_uuid=True), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    PrimaryKeyConstraint(
        "corporate_id",
        "legacy_parent_record_id",
        "legacy_tracing_report_id",
        name="pk_legacy_tracing_report_links",
    ),
    ForeignKeyConstraint(
        ["legacy_parent_record_id"],
        ["medication_history_records.id"],
        name="fk_legacy_tracing_report_links_parent",
    ),
    ForeignKeyConstraint(
        ["target_record_id"],
        ["medication_history_records.id"],
        name="fk_legacy_tracing_report_links_target",
    ),
)

# 確定済の初回薬歴だけを1件に制限する。フォローアップは複数作成できる。
Index(
    "uq_medication_history_records_finalized_dispensing",
    medication_history_records.c.corporate_id,
    medication_history_records.c.dispensing_id,
    unique=True,
    postgresql_where=(
        (medication_history_records.c.status == "finalized")
        & medication_history_records.c.dispensing_id.is_not(None)
    ),
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

medication_history_category_catalogs = Table(
    "medication_history_category_catalogs",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
    Column("corporate_id", UUID(as_uuid=True), nullable=False),
    Column("payload", JSONB, nullable=False),
    Column("version", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint(
        "corporate_id", name="uq_medication_history_category_catalogs_corporate"
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
    """CREATE OR REPLACE FUNCTION protect_care_event_identity() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION '業務Eventは削除できません。' USING ERRCODE = '23514', CONSTRAINT = 'ck_care_events_immutable';
        END IF;
        IF NEW.id IS DISTINCT FROM OLD.id OR NEW.event_type_id IS DISTINCT FROM OLD.event_type_id OR NEW.event_definition_corporate_id IS DISTINCT FROM OLD.event_definition_corporate_id OR NEW.event_type_standard_code IS DISTINCT FROM OLD.event_type_standard_code OR NEW.event_type_name IS DISTINCT FROM OLD.event_type_name OR NEW.corporate_id IS DISTINCT FROM OLD.corporate_id OR NEW.store_id IS DISTINCT FROM OLD.store_id OR NEW.patient_id IS DISTINCT FROM OLD.patient_id OR NEW.created_at IS DISTINCT FROM OLD.created_at OR NEW.related_event_id IS DISTINCT FROM OLD.related_event_id OR NEW.reception_id IS DISTINCT FROM OLD.reception_id OR NEW.prescription_id IS DISTINCT FROM OLD.prescription_id OR NEW.dispensing_id IS DISTINCT FROM OLD.dispensing_id OR (NEW.payload - 'occurred_at') IS DISTINCT FROM (OLD.payload - 'occurred_at') THEN
            RAISE EXCEPTION '業務Eventの内容と参照は変更できません。' USING ERRCODE = '23514', CONSTRAINT = 'ck_care_events_immutable';
        END IF;
        IF OLD.occurred_at_is_unknown AND OLD.occurred_at IS NULL AND NOT NEW.occurred_at_is_unknown AND NEW.occurred_at IS NOT NULL THEN
            RETURN NEW;
        END IF;
        RAISE EXCEPTION '業務Eventの発生日時は時刻不明から一度だけ確定できます。' USING ERRCODE = '23514', CONSTRAINT = 'ck_care_events_immutable';
    END;
    $$""",
    "CREATE TRIGGER care_events_immutable BEFORE UPDATE OR DELETE ON care_events FOR EACH ROW EXECUTE FUNCTION protect_care_event_identity()",
    """CREATE OR REPLACE FUNCTION protect_reception_event_association() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        IF OLD.event_id IS NOT NULL AND NEW.event_id IS DISTINCT FROM OLD.event_id THEN
            RAISE EXCEPTION '受付のEvent関連は付け替えできません。' USING ERRCODE = '23514', CONSTRAINT = 'ck_receptions_event_immutable';
        END IF;
        RETURN NEW;
    END;
    $$""",
    "CREATE TRIGGER receptions_event_immutable BEFORE UPDATE ON receptions FOR EACH ROW EXECUTE FUNCTION protect_reception_event_association()",
    """CREATE OR REPLACE FUNCTION prevent_legacy_archive_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        RAISE EXCEPTION '移行アーカイブは追記専用です。' USING ERRCODE = '23514', CONSTRAINT = 'ck_medication_history_legacy_archive_immutable';
    END;
    $$""",
    "CREATE TRIGGER medication_history_legacy_archives_immutable BEFORE UPDATE OR DELETE ON medication_history_legacy_archives FOR EACH ROW EXECUTE FUNCTION prevent_legacy_archive_mutation()",
    "CREATE TRIGGER legacy_tracing_report_links_immutable BEFORE UPDATE OR DELETE ON legacy_tracing_report_links FOR EACH ROW EXECUTE FUNCTION prevent_legacy_archive_mutation()",
    """CREATE OR REPLACE FUNCTION check_care_event_type_scope() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        IF NEW.event_definition_corporate_id IS NULL THEN
            IF NOT EXISTS (
                SELECT 1 FROM event_definitions
                WHERE id = NEW.event_type_id AND corporate_id IS NULL
            ) THEN
                RAISE EXCEPTION '標準Event種別の定義が存在しないか、法人が一致しません。' USING ERRCODE = '23514', CONSTRAINT = 'ck_care_events_event_type_scope';
            END IF;
        ELSE
            IF NOT EXISTS (
                SELECT 1 FROM event_definitions
                WHERE id = NEW.event_type_id AND corporate_id = NEW.corporate_id
            ) THEN
                RAISE EXCEPTION '法人固有Event種別の定義が存在しないか、法人が一致しません。' USING ERRCODE = '23514', CONSTRAINT = 'ck_care_events_event_type_scope';
            END IF;
        END IF;
        RETURN NEW;
    END;
    $$""",
    "CREATE TRIGGER care_events_event_type_scope_guard BEFORE INSERT OR UPDATE ON care_events FOR EACH ROW EXECUTE FUNCTION check_care_event_type_scope()",
    """CREATE OR REPLACE FUNCTION check_care_event_reception_consistency() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE
        v_reception RECORD;
    BEGIN
        IF NEW.reception_id IS NULL THEN
            RETURN NEW;
        END IF;

        SELECT payload
        INTO v_reception
        FROM receptions
        WHERE corporate_id = NEW.corporate_id
          AND store_id = NEW.store_id
          AND id = NEW.reception_id
        FOR KEY SHARE;

        IF NOT FOUND THEN
            RETURN NEW;
        END IF;

        IF NULLIF(v_reception.payload->>'patient_id', '')::uuid IS DISTINCT FROM NEW.patient_id
           OR NULLIF(v_reception.payload->>'prescription_id', '')::uuid IS DISTINCT FROM NEW.prescription_id
           OR NULLIF(v_reception.payload->>'dispensing_id', '')::uuid IS DISTINCT FROM NEW.dispensing_id THEN
            RAISE EXCEPTION '受付と業務Eventの患者・処方・調剤参照が一致しません。' USING ERRCODE = '23514', CONSTRAINT = 'ck_care_events_reception_resources';
        END IF;
        RETURN NEW;
    END;
    $$""",
    "CREATE TRIGGER care_events_reception_resources_guard BEFORE INSERT OR UPDATE ON care_events FOR EACH ROW EXECUTE FUNCTION check_care_event_reception_consistency()",
    """CREATE OR REPLACE FUNCTION check_reception_care_event_consistency() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE
        v_event RECORD;
    BEGIN
        IF NEW.event_id IS NULL THEN
            RETURN NEW;
        END IF;

        SELECT patient_id, prescription_id, dispensing_id
        INTO v_event
        FROM care_events
        WHERE id = NEW.event_id
        FOR KEY SHARE;

        IF NOT FOUND THEN
            RETURN NEW;
        END IF;

        IF NULLIF(NEW.payload->>'patient_id', '')::uuid IS DISTINCT FROM v_event.patient_id
           OR NULLIF(NEW.payload->>'prescription_id', '')::uuid IS DISTINCT FROM v_event.prescription_id
           OR NULLIF(NEW.payload->>'dispensing_id', '')::uuid IS DISTINCT FROM v_event.dispensing_id THEN
            RAISE EXCEPTION '受付と業務Eventの患者・処方・調剤参照が一致しません。' USING ERRCODE = '23514', CONSTRAINT = 'ck_receptions_event_resources';
        END IF;
        RETURN NEW;
    END;
    $$""",
    "CREATE TRIGGER receptions_event_resources_guard BEFORE INSERT OR UPDATE ON receptions FOR EACH ROW EXECUTE FUNCTION check_reception_care_event_consistency()",
    """CREATE OR REPLACE FUNCTION check_medication_history_event_resources() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE
        v_event RECORD;
    BEGIN
        SELECT prescription_id, dispensing_id, corporate_id, store_id, patient_id
        INTO v_event
        FROM care_events
        WHERE id = NEW.event_id;

        IF NOT FOUND THEN
            RAISE EXCEPTION '関連する業務Eventが存在しません。' USING ERRCODE = '23503', CONSTRAINT = 'fk_medication_history_records_event_scope';
        END IF;

        IF NEW.corporate_id IS DISTINCT FROM v_event.corporate_id
           OR NEW.store_id IS DISTINCT FROM v_event.store_id
           OR NEW.patient_id IS DISTINCT FROM v_event.patient_id THEN
            RAISE EXCEPTION '薬歴と業務Eventの所属範囲が一致しません。' USING ERRCODE = '23514', CONSTRAINT = 'ck_medication_history_records_event_scope';
        END IF;

        IF NEW.prescription_id IS DISTINCT FROM v_event.prescription_id
           OR NEW.dispensing_id IS DISTINCT FROM v_event.dispensing_id THEN
            RAISE EXCEPTION '薬歴と業務Eventの処方・調剤参照が一致しません。' USING ERRCODE = '23514', CONSTRAINT = 'ck_medication_history_records_event_resources';
        END IF;

        RETURN NEW;
    END;
    $$""",
    "CREATE TRIGGER medication_history_event_resources_guard BEFORE INSERT OR UPDATE ON medication_history_records FOR EACH ROW EXECUTE FUNCTION check_medication_history_event_resources()",
)
