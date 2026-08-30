"""テーブル定義・マイグレーション・Repositoryが書く列の三者一致を検査する。

集約をJSONBの1行として保存する設計では、Repositoryが書こうとする列がテーブルに
無くても、テーブルを作るのはマイグレーション、列を決めるのはスキーマ定義、値を
組み立てるのはRepositoryと持ち場が分かれているため、どの単体テストにも掛からない。
実DBに繋いで初めて落ちる種類の食い違いなので、DBなしで検出できる形にしておく。
"""

from __future__ import annotations

import io
from collections.abc import Mapping
from datetime import UTC, datetime

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Table
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.schema import CreateIndex, CreateTable

from app.infrastructure.postgres import schema
from app.infrastructure.postgres.repositories import (
    corporate as corporate_repository,
)
from app.infrastructure.postgres.repositories import (
    coverage as coverage_repository,
)
from app.infrastructure.postgres.repositories import (
    dispensing as dispensing_repository,
)
from app.infrastructure.postgres.repositories import (
    medication_history as medication_history_repository,
)
from app.infrastructure.postgres.repositories import (
    medicine_catalog as medicine_catalog_repository,
)
from app.infrastructure.postgres.repositories import (
    patient as patient_repository,
)
from app.infrastructure.postgres.repositories import (
    prescription as prescription_repository,
)
from app.infrastructure.postgres.repositories import (
    reception as reception_repository,
)
from app.infrastructure.postgres.repositories import staff as staff_repository
from app.infrastructure.postgres.repositories import store as store_repository
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


def _row_value_cases() -> list[tuple[str, Table, Mapping[str, object]]]:
    """各Repositoryが1行に書く値を、対応するテーブルと組にして返す。"""
    return [
        (
            "corporates",
            schema.corporates,
            corporate_repository.row_values(create_corporate()),
        ),
        (
            "prescriptions",
            schema.prescriptions,
            prescription_repository.row_values(create_prescription()),
        ),
        (
            "dispensing_processes",
            schema.dispensing_processes,
            dispensing_repository.row_values(create_dispensing()),
        ),
        ("stores", schema.stores, store_repository.row_values(create_store())),
        (
            "staff_members",
            schema.staff_members,
            staff_repository.row_values(create_staff()),
        ),
        (
            "patients",
            schema.patients,
            patient_repository.row_values(create_patient()),
        ),
        (
            "patient_external_identifiers",
            schema.patient_external_identifiers,
            patient_repository.identifier_row_values(create_external_identifier()),
        ),
        (
            "patient_coverages",
            schema.patient_coverages,
            coverage_repository.row_values(create_coverage()),
        ),
        (
            "coverage_selection_records",
            schema.coverage_selection_records,
            reception_repository.row_values(create_selection_record()),
        ),
        (
            "medication_history_records",
            schema.medication_history_records,
            medication_history_repository.row_values(create_record()),
        ),
        (
            "patient_medical_profiles",
            schema.patient_medical_profiles,
            medication_history_repository.profile_row_values(create_medical_profile()),
        ),
        (
            "medicines",
            schema.medicines,
            medicine_catalog_repository.row_values(create_medicine()),
        ),
    ]


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


def _migration_ddl() -> set[str]:
    """全マイグレーションを適用した結果のDDLを集める。

    拡張の作成は表の形を決めないので比較対象から外す。
    """
    return {
        statement
        for statement in _normalized_statements(_run_offline("upgrade"))
        if not statement.startswith("CREATE EXTENSION")
    }


def _schema_ddl() -> set[str]:
    """スキーマ定義から、同じ形のDDLを生成する。"""
    statements: set[str] = set()
    for table in schema.metadata.sorted_tables:
        statements.add(_normalized_statement(compiled_sql(CreateTable(table))))
        for index in table.indexes:
            statements.add(_normalized_statement(compiled_sql(CreateIndex(index))))
    return statements


@pytest.mark.parametrize(
    ("table_name", "table", "values"),
    _row_value_cases(),
    ids=lambda value: value if isinstance(value, str) else "",
)
def test_Repositoryが書く列が_テーブル定義に存在する(
    table_name: str, table: Table, values: Mapping[str, object]
) -> None:
    """定義に無い列へ書こうとすると、文の組み立て時点で失敗する。"""
    # Arrange
    now = datetime.now(UTC)

    # Act
    statement = postgres_insert(table).values(
        **values, version=1, created_at=now, updated_at=now
    )

    # Assert
    assert table_name in compiled_sql(statement)


@pytest.mark.parametrize(
    ("table_name", "table", "values"),
    _row_value_cases(),
    ids=lambda value: value if isinstance(value, str) else "",
)
def test_NOT_NULLの列が_保存時にすべて埋まる(
    table_name: str, table: Table, values: Mapping[str, object]
) -> None:
    """既定値を持たない必須列は、Repositoryかupsertのどちらかが必ず埋める。"""
    # Arrange
    required = {
        column.name
        for column in table.columns
        if not column.nullable
        and column.default is None
        and column.server_default is None
    }

    # Act
    supplied = set(values) | _MANAGED_COLUMNS

    # Assert
    assert required <= supplied, (
        f"{table_name} の必須列 {sorted(required - supplied)} が保存時に埋まりません。"
    )


@pytest.mark.parametrize(
    ("table_name", "table", "values"),
    _row_value_cases(),
    ids=lambda value: value if isinstance(value, str) else "",
)
def test_Repositoryが書く列に_未知の列が混ざらない(
    table_name: str, table: Table, values: Mapping[str, object]
) -> None:
    """テーブルに無い列名を書くと、実行時までエラーが遅れるので事前に落とす。"""
    # Arrange
    defined = {column.name for column in table.columns}

    # Act
    unknown = set(values) - defined

    # Assert
    assert not unknown, (
        f"{table_name} に存在しない列へ書こうとしています: {sorted(unknown)}"
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
    assert declared == {"patient_number_sequences"}
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
        assert f"DROP TABLE {table.name}" in dropped
