"""テーブル定義・マイグレーション・Repositoryが書く列の三者一致を検査する。

集約をJSONBの1行として保存する設計では、Repositoryが書こうとする列がテーブルに
無くても、テーブルを作るのはマイグレーション、列を決めるのはスキーマ定義、値を
組み立てるのはRepositoryと持ち場が分かれているため、どの単体テストにも掛からない。
実DBに繋いで初めて落ちる種類の食い違いなので、DBなしで検出できる形にしておく。
"""

from __future__ import annotations

import importlib
import io
import pkgutil
from collections.abc import Mapping
from datetime import UTC, date, datetime
from typing import Any

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Table
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.schema import CreateIndex, CreateTable

from app.domain.identity.account_person import AccountPerson
from app.domain.identity.invitation import InvitationDigest, UserInvitation
from app.domain.identity.membership import CorporateMembership
from app.domain.identity.primitives import (
    AccountPersonId,
    CorporateMembershipId,
    MembershipRole,
    UserAccountId,
    UserInvitationId,
)
from app.domain.identity.staff_person_link import StaffPersonLink
from app.domain.identity.user_account import UserAccount
from app.domain.medication_history.category_catalog import (
    MedicationHistoryCategoryCatalog,
)
from app.domain.shared.person_name import PersonNames
from app.domain.store.manager_assignment import (
    ManagerAssignmentPeriod,
    StoreManagerAssignment,
    StoreManagerAssignmentId,
)
from app.infrastructure.postgres import repositories, schema
from app.infrastructure.postgres.repositories.account_person import (
    ACCOUNT_PERSON_MAPPING,
)
from app.infrastructure.postgres.repositories.corporate import CORPORATE_MAPPING
from app.infrastructure.postgres.repositories.corporate_membership import (
    MEMBERSHIP_MAPPING,
)
from app.infrastructure.postgres.repositories.coverage_selection_record import (
    COVERAGE_SELECTION_RECORD_MAPPING,
)
from app.infrastructure.postgres.repositories.dispensing_process import (
    DISPENSING_PROCESS_MAPPING,
)
from app.infrastructure.postgres.repositories.medication_history import (
    MEDICATION_HISTORY_RECORD_MAPPING,
)
from app.infrastructure.postgres.repositories.medication_history_category_catalog import (
    MEDICATION_HISTORY_CATEGORY_CATALOG_MAPPING,
)
from app.infrastructure.postgres.repositories.medicine_catalog import MEDICINE_MAPPING
from app.infrastructure.postgres.repositories.patient import PATIENT_MAPPING
from app.infrastructure.postgres.repositories.patient_coverage import (
    PATIENT_COVERAGE_MAPPING,
)
from app.infrastructure.postgres.repositories.patient_external_identifier import (
    PATIENT_EXTERNAL_IDENTIFIER_MAPPING,
)
from app.infrastructure.postgres.repositories.patient_medical_profile import (
    PATIENT_MEDICAL_PROFILE_MAPPING,
)
from app.infrastructure.postgres.repositories.prescription import PRESCRIPTION_MAPPING
from app.infrastructure.postgres.repositories.staff import STAFF_MAPPING
from app.infrastructure.postgres.repositories.staff_person_link import (
    STAFF_PERSON_LINK_MAPPING,
)
from app.infrastructure.postgres.repositories.store import STORE_MAPPING
from app.infrastructure.postgres.repositories.store_manager_assignment import (
    MANAGER_ASSIGNMENT_MAPPING,
)
from app.infrastructure.postgres.repositories.user_account import USER_ACCOUNT_MAPPING
from app.infrastructure.postgres.repositories.user_invitation import INVITATION_MAPPING
from app.infrastructure.postgres.repository_base import AggregateMapping
from tests.factories.dispensing_factory import create_dispensing
from tests.factories.medication_history_factory import create_record
from tests.factories.medicine_catalog_factory import create_medicine
from tests.factories.persistence_factory import (
    create_coverage,
    create_external_identifier,
    create_medical_profile,
    create_patient,
    create_selection_record,
)
from tests.factories.prescription_factory import create_prescription
from tests.factories.staff_factory import create_staff
from tests.factories.store_factory import create_store
from tests.infrastructure.postgres.helpers import (
    compiled_sql,
    create_corporate,
    ordered_migrations,
    postgres_dialect,
)

_MIGRATIONS_PACKAGE = "migrations.versions"

# upsert が列名以外に必ず埋める列。Repositoryのvaluesには現れない。
_MANAGED_COLUMNS = frozenset({"version", "created_at", "updated_at"})


def _case[AggregateT](
    mapping: AggregateMapping[AggregateT], aggregate: AggregateT
) -> tuple[AggregateMapping[Any], Mapping[str, object]]:
    """対応を検査する組を作る。

    ``mapping`` と ``aggregate`` の型が食い違う組は型検査で落ちるので、別集約の
    見本を渡したまま「列は存在する」という無意味な検査が緑になることはない。
    """
    return mapping, mapping.row_values(aggregate)


def _row_value_cases() -> list[tuple[AggregateMapping[Any], Mapping[str, object]]]:
    """各Repositoryが1行に書く値を、対応と組にして返す。"""
    person = AccountPerson(
        id=AccountPersonId.generate(),
        names=PersonNames.create(
            last_name="山田",
            first_name="太郎",
            last_name_kana="ヤマダ",
            first_name_kana="タロウ",
        ),
    )
    account = UserAccount(id=UserAccountId.generate(), person_id=person.id)
    store = create_store()
    staff = create_staff()
    return [
        _case(ACCOUNT_PERSON_MAPPING, person),
        _case(USER_ACCOUNT_MAPPING, account),
        _case(
            MEMBERSHIP_MAPPING,
            CorporateMembership(
                id=CorporateMembershipId.generate(),
                account_id=account.id,
                corporate_id=store.corporate_id,
                role=MembershipRole.CORPORATE_ADMIN,
                store_ids=frozenset(),
            ),
        ),
        _case(
            STAFF_PERSON_LINK_MAPPING,
            StaffPersonLink(
                id=staff.id, person_id=person.id, corporate_id=staff.corporate_id
            ),
        ),
        _case(
            INVITATION_MAPPING,
            UserInvitation(
                id=UserInvitationId.generate(),
                person_id=person.id,
                corporate_id=store.corporate_id,
                role=MembershipRole.CORPORATE_ADMIN,
                store_ids=frozenset(),
                secret_digest=InvitationDigest("a" * 64),
                expires_at=datetime(2026, 9, 20, tzinfo=UTC),
            ),
        ),
        _case(
            MANAGER_ASSIGNMENT_MAPPING,
            StoreManagerAssignment(
                id=StoreManagerAssignmentId.generate(),
                corporate_id=store.corporate_id,
                store_id=store.id,
                staff_id=staff.id,
                person_id=AccountPersonId.generate(),
                period=ManagerAssignmentPeriod(starts_on=date(2026, 9, 17)),
            ),
        ),
        _case(CORPORATE_MAPPING, create_corporate()),
        _case(STORE_MAPPING, create_store()),
        _case(STAFF_MAPPING, create_staff()),
        _case(PATIENT_MAPPING, create_patient()),
        _case(PATIENT_EXTERNAL_IDENTIFIER_MAPPING, create_external_identifier()),
        _case(PATIENT_COVERAGE_MAPPING, create_coverage()),
        _case(COVERAGE_SELECTION_RECORD_MAPPING, create_selection_record()),
        _case(PRESCRIPTION_MAPPING, create_prescription()),
        _case(DISPENSING_PROCESS_MAPPING, create_dispensing()),
        _case(MEDICATION_HISTORY_RECORD_MAPPING, create_record()),
        _case(
            MEDICATION_HISTORY_CATEGORY_CATALOG_MAPPING,
            MedicationHistoryCategoryCatalog.create_default(
                corporate_id=store.corporate_id
            ),
        ),
        _case(PATIENT_MEDICAL_PROFILE_MAPPING, create_medical_profile()),
        _case(MEDICINE_MAPPING, create_medicine()),
    ]


def _declared_mappings() -> list[AggregateMapping[Any]]:
    """``app/infrastructure/postgres/repositories`` の全ての対応を集める。"""
    # SQLAlchemy の ``Table`` は ``==`` がSQL式を作るので、値としては比較できない。
    # 同じ対応を複数のモジュールから見ても1つに畳めるよう、同一性で束ねる。
    found: dict[int, AggregateMapping[Any]] = {}
    for module_info in pkgutil.walk_packages(
        repositories.__path__, prefix=f"{repositories.__name__}."
    ):
        module = importlib.import_module(module_info.name)
        for value in vars(module).values():
            if isinstance(value, AggregateMapping):
                found[id(value)] = value
    return list(found.values())


def _case_id(value: object) -> str:
    """テーブル名をテストIDにする。"""
    return value.table.name if isinstance(value, AggregateMapping) else ""


def _top_level_items(body: str) -> list[str]:
    """括弧の外側にあるカンマで区切る。列や制約の定義を1つずつ取り出すため。"""
    items: list[str] = []
    depth = 0
    current: list[str] = []
    for character in body:
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
        if character == "," and depth == 0:
            items.append("".join(current).strip())
            current = []
            continue
        current.append(character)
    tail = "".join(current).strip()
    if tail:
        items.append(tail)
    return items


def _normalized_statement(statement: str) -> str:
    """1文を、意味が同じなら同じ文字列になる形へ正規化する。

    ``CREATE TABLE`` の中の列と制約は、書いた順にそのままSQLへ出る。並び順は
    テーブルの意味を変えないので、順序の違いだけで差分として報告されないよう
    並べ替える。順序まで固定すると、制約を1つ足すたびに無関係な失敗が出る。
    """
    collapsed = " ".join(statement.split())
    if not collapsed.upper().startswith("CREATE TABLE"):
        return collapsed
    open_index = collapsed.find("(")
    close_index = collapsed.rfind(")")
    if open_index == -1 or close_index <= open_index:
        return collapsed
    head = collapsed[:open_index].strip()
    body = collapsed[open_index + 1 : close_index]
    tail = collapsed[close_index + 1 :].strip()
    items = sorted(_top_level_items(body))
    return f"{head} ( {', '.join(items)} ){tail}".strip()


def _normalized_statements(sql: str) -> set[str]:
    """SQL文字列を、正規化した文単位の集合へ変換する。"""
    return {_normalized_statement(part) for part in sql.split(";") if part.strip()}


def _run_offline(operation_name: str) -> str:
    """全マイグレーションをオフラインで実行し、生成されるSQLを返す。"""
    buffer = io.StringIO()
    context = MigrationContext.configure(
        dialect=postgres_dialect(),
        opts={"as_sql": True, "output_buffer": buffer},
    )
    modules = ordered_migrations()
    if operation_name == "downgrade":
        modules = list(reversed(modules))
    with Operations.context(context):
        for module in modules:
            getattr(module, operation_name)()
    return buffer.getvalue()


#: 表の形を決めないので突き合わせから外す文。
#:
#: 拡張の有効化は環境の準備であり、``UPDATE`` 等はデータの移行である。
#: 「対象外」をこの2種類に限ることで、新しい**DDL**の形（``ALTER TABLE ... ADD
#: CONSTRAINT`` や関数・トリガ）が黙って検査の外へ出ることがなくなる。
_IGNORED_MIGRATION_PREFIXES = ("CREATE EXTENSION", "UPDATE ", "INSERT ", "DELETE ")

#: 突き合わせの対象にするDDLの形。
_COMPARED_DDL_PREFIXES = ("CREATE TABLE", "CREATE INDEX", "CREATE UNIQUE INDEX")


def _split_statements(sql: str) -> list[str]:
    """``$$`` で囲まれた本体の中の ``;`` で切らずに文へ分ける。

    plpgsql の本体には ``;`` が含まれる。素朴に分割すると関数定義が断片になり、
    比較しても意味を持たない。
    """
    statements: list[str] = []
    current: list[str] = []
    in_body = False
    index = 0
    while index < len(sql):
        if sql.startswith("$$", index):
            in_body = not in_body
            current.append("$$")
            index += 2
            continue
        character = sql[index]
        if character == ";" and not in_body:
            statements.append("".join(current))
            current = []
        else:
            current.append(character)
        index += 1
    statements.append("".join(current))
    return [item for item in statements if item.strip()]


def _upgrade_statements() -> list[str]:
    """マイグレーションが出す文を、正規化して順に返す。"""
    return [
        _normalized_statement(item)
        for item in _split_statements(_run_offline("upgrade"))
    ]


def _migration_ddl() -> set[str]:
    """マイグレーションが作る表と索引のDDLを集める。"""
    return {
        statement
        for statement in _upgrade_statements()
        if statement.startswith(_COMPARED_DDL_PREFIXES)
    }


def _schema_ddl() -> set[str]:
    """スキーマ定義から、同じ形のDDLを生成する。"""
    statements: set[str] = set()
    for table in schema.metadata.sorted_tables:
        statements.add(_normalized_statement(compiled_sql(CreateTable(table))))
        for index in table.indexes:
            statements.add(_normalized_statement(compiled_sql(CreateIndex(index))))
    return statements


def _declared_routines() -> set[str]:
    """スキーマ定義が宣言する関数・トリガを正規化して返す。"""
    return {_normalized_statement(item) for item in schema.SCHEMA_ROUTINES}


def test_マイグレーションの全DDLが_検査の対象になっている() -> None:
    """検査の網から外れるDDLの形を作らせない。

    以前は突き合わせの対象を CREATE TABLE / INDEX だけに絞っていたため、関数と
    トリガ（Repositoryが制約名で業務例外へ写像している保護）が一切検査されず、
    名前を変えても対応が切れたことに気づけなかった。分類できない文が現れたら
    落とし、対象にするか宣言するかを選ばせる。
    """
    # Arrange
    routines = _declared_routines()

    # Act
    unclassified = [
        statement
        for statement in _upgrade_statements()
        if not statement.startswith(_IGNORED_MIGRATION_PREFIXES)
        and not statement.startswith(_COMPARED_DDL_PREFIXES)
        and statement not in routines
    ]

    # Assert
    assert not unclassified, f"検査の対象になっていないDDL: {unclassified}"


def test_スキーマ定義の関数とトリガが_マイグレーションと一致する() -> None:
    """片方だけを直すと、制約名と業務例外の対応が静かに切れる。"""
    # Arrange
    declared = _declared_routines()

    # Act
    emitted = {
        statement
        for statement in _upgrade_statements()
        if statement.startswith(("CREATE OR REPLACE FUNCTION", "CREATE TRIGGER"))
    }

    # Assert
    assert emitted == declared, (
        f"スキーマ定義にだけある: {sorted(declared - emitted)} / "
        f"マイグレーションにだけある: {sorted(emitted - declared)}"
    )


@pytest.mark.parametrize(
    ("mapping", "values"),
    _row_value_cases(),
    ids=_case_id,
)
def test_Repositoryが書く列が_テーブル定義に存在する(
    mapping: AggregateMapping[Any], values: Mapping[str, object]
) -> None:
    """定義に無い列へ書こうとすると、文の組み立て時点で失敗する。"""
    # Arrange
    now = datetime.now(UTC)

    # Act
    statement = postgres_insert(mapping.table).values(
        **values, version=1, created_at=now, updated_at=now
    )

    # Assert
    assert mapping.table.name in compiled_sql(statement)


@pytest.mark.parametrize(
    ("mapping", "values"),
    _row_value_cases(),
    ids=_case_id,
)
def test_NOT_NULLの列が_保存時にすべて埋まる(
    mapping: AggregateMapping[Any], values: Mapping[str, object]
) -> None:
    """既定値を持たない必須列は、Repositoryかupsertのどちらかが必ず埋める。"""
    # Arrange
    required = {
        column.name
        for column in mapping.table.columns
        if not column.nullable
        and column.default is None
        and column.server_default is None
    }

    # Act
    supplied = set(values) | _MANAGED_COLUMNS

    # Assert
    assert required <= supplied, (
        f"{mapping.table.name} の必須列 {sorted(required - supplied)} が保存時に埋まりません。"
    )


@pytest.mark.parametrize(
    ("mapping", "values"),
    _row_value_cases(),
    ids=_case_id,
)
def test_Repositoryが書く列に_未知の列が混ざらない(
    mapping: AggregateMapping[Any], values: Mapping[str, object]
) -> None:
    """テーブルに無い列名を書くと、実行時までエラーが遅れるので事前に落とす。"""
    # Arrange
    defined = {column.name for column in mapping.table.columns}

    # Act
    unknown = set(values) - defined

    # Assert
    assert not unknown, (
        f"{mapping.table.name} に存在しない列へ書こうとしています: {sorted(unknown)}"
    )


def test_マイグレーションのDDLが_スキーマ定義と一致する() -> None:
    """スキーマ定義に列を足してマイグレーションを直し忘れると落ちる。"""
    # Arrange
    expected = _schema_ddl()

    # Act
    actual = _migration_ddl()

    # Assert
    assert actual == expected, (
        "マイグレーションとスキーマ定義が食い違っています。\n"
        f"スキーマ定義にだけある: {sorted(expected - actual)}\n"
        f"マイグレーションにだけある: {sorted(actual - expected)}"
    )


def _aggregate_tables() -> list[Table]:
    """集約を保存するテーブルだけを返す。"""
    return [
        table
        for table in schema.metadata.sorted_tables
        if table.name not in schema.NON_AGGREGATE_TABLES
    ]


def test_集約でないテーブルの一覧が_明示的に宣言されている() -> None:
    """payload も version も持たない表は例外なので、増やすなら宣言を伴わせる。

    宣言せずに追加すると、集約テーブルの検査から静かに抜け落ちる。
    """
    # Arrange
    declared = set(schema.NON_AGGREGATE_TABLES)

    # Act
    existing = {table.name for table in schema.metadata.sorted_tables}

    # Assert
    assert declared == {"patient_number_sequences", "operation_audits"}
    assert declared <= existing, (
        f"宣言だけあって実在しないテーブル: {sorted(declared - existing)}"
    )


def test_集約テーブルが_楽観ロック用のversion列を持つ() -> None:
    """集約を1行のJSONBで持つ以上、後勝ちの上書きを検出する列が要る。"""
    # Arrange
    tables = _aggregate_tables()

    # Act
    missing = [table.name for table in tables if "version" not in table.columns]

    # Assert
    assert not missing, f"version列が無いテーブル: {missing}"


def test_集約テーブルが_payload列を持つ() -> None:
    """検索列だけでは集約を復元できないため、payloadは全テーブルに要る。"""
    # Arrange
    tables = _aggregate_tables()

    # Act
    missing = [table.name for table in tables if "payload" not in table.columns]

    # Assert
    assert not missing, f"payload列が無いテーブル: {missing}"


def test_マイグレーションのdowngradeが_全テーブルを削除する() -> None:
    """upgradeで作った表が残ると、やり直しのたびに手作業が要る。"""
    # Arrange
    buffer = io.StringIO()
    context = MigrationContext.configure(
        dialect=postgres_dialect(),
        opts={"as_sql": True, "output_buffer": buffer},
    )
    del buffer, context

    # Act
    dropped = _run_offline("downgrade")

    # Assert
    for table in schema.metadata.sorted_tables:
        assert f"DROP TABLE {table.name}" in dropped.replace('"', "")


def test_全ての集約対応が_列の検査対象になっている() -> None:
    """Repositoryを足して検査へ入れ忘れると落ちる。

    ここが手作業の一覧のままだと、新しい集約の列が「テーブルに存在するか」も
    「必須列が埋まるか」も確かめられないまま緑になる。実DBに繋ぐまで誰も
    気づかない種類の抜けなので、登録簿そのものと突き合わせる。
    """
    # Arrange
    declared = {mapping.table.name for mapping in _declared_mappings()}

    # Act
    covered = {mapping.table.name for mapping, _ in _row_value_cases()}

    # Assert
    assert declared == covered, (
        f"検査されていない集約: {sorted(declared - covered)} / "
        f"実在しない集約: {sorted(covered - declared)}"
    )
