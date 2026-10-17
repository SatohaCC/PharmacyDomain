"""Event集約のテーブルと店舗読取条件を検証する。"""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import (
    ForeignKeyConstraint,
    Index,
    Select,
    Table,
    UniqueConstraint,
    select,
)

from app.infrastructure.postgres import schema
from app.infrastructure.postgres.read_scope import RepositoryReadScope

_SCOPE = RepositoryReadScope(
    corporate_id=UUID("01890000-0000-7000-8000-000000000000"),
    store_ids=(UUID("01890000-0000-7000-8000-000000000001"),),
    applied_on=date(2026, 9, 26),
    person_id=UUID("01890000-0000-7000-8000-0000000000a0"),
    account_id=UUID("01890000-0000-7000-8000-0000000000a1"),
)


def _compiled(table: Table, statement: Select[Any]) -> str:
    return str(_SCOPE.apply(table, statement).compile())


def test_tc45_59_Eventと種別のschemaおよび薬歴参照列がある() -> None:
    tables = schema.metadata.tables
    missing = {"event_definitions", "care_events"} - set(tables)
    assert missing == set(), f"Event用のテーブルが未定義: {sorted(missing)}"
    assert "event_id" in tables["medication_history_records"].c


def test_tc45_08_Eventの種別参照は同じ法人か標準定義に限る() -> None:
    definition = schema.metadata.tables.get("event_definitions")
    event = schema.metadata.tables.get("care_events")
    assert definition is not None, "Event種別テーブルが未定義"
    assert event is not None, "Eventテーブルが未定義"

    foreign_keys = [
        constraint
        for constraint in event.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    ]
    assert any(
        [element.parent.name for element in constraint.elements] == ["event_type_id"]
        and constraint.referred_table is definition
        for constraint in foreign_keys
    )
    assert any(
        [element.parent.name for element in constraint.elements]
        == ["event_type_id", "event_definition_corporate_id"]
        and constraint.referred_table is definition
        for constraint in foreign_keys
    )
    assert {"corporate_id", "event_type_id"} <= set(event.c.keys())


def test_tc45_04_標準種別コードにDB一意性がある() -> None:
    definition = schema.metadata.tables.get("event_definitions")
    assert definition is not None, "Event種別テーブルが未定義"
    assert any(
        index.unique
        and tuple(column.name for column in index.columns) == ("standard_code",)
        for index in definition.indexes
        if isinstance(index, Index)
    )


def test_tc45_16_Event関連参照は法人患者の複合参照である() -> None:
    event = schema.metadata.tables.get("care_events")
    assert event is not None, "Eventテーブルが未定義"

    foreign_keys = [
        constraint
        for constraint in event.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    ]
    assert any(
        [column.name for column in constraint.columns]
        == ["related_event_id", "corporate_id", "patient_id"]
        and constraint.referred_table is event
        for constraint in foreign_keys
    )


def test_tc45_18_Eventの受付処方調剤参照がDBに宣言される() -> None:
    event = schema.metadata.tables.get("care_events")
    assert event is not None, "Eventテーブルが未定義"
    referenced_tables = {
        element.column.table.name
        for constraint in event.constraints
        if isinstance(constraint, ForeignKeyConstraint)
        for element in constraint.elements
    }

    assert {"receptions", "prescriptions", "dispensing_processes"} <= referenced_tables


def test_tc45_21_22_23_Eventと薬歴の1対1および識別整合がある() -> None:
    history = schema.metadata.tables["medication_history_records"]
    event = schema.metadata.tables.get("care_events")
    assert event is not None, "Eventテーブルが未定義"
    assert {"event_id", "corporate_id", "store_id", "patient_id"} <= set(
        history.c.keys()
    )
    assert any(
        isinstance(constraint, UniqueConstraint)
        and tuple(column.name for column in constraint.columns) == ("event_id",)
        for constraint in history.constraints
    )
    assert any(
        isinstance(constraint, ForeignKeyConstraint)
        and constraint.referred_table is event
        for constraint in history.constraints
    )


def test_tc45_39_ReceptionはEventと一意に関連付けられる() -> None:
    reception = schema.metadata.tables["receptions"]
    event = schema.metadata.tables.get("care_events")
    assert event is not None, "Eventテーブルが未定義"
    assert "event_id" in reception.c
    assert any(
        isinstance(constraint, UniqueConstraint)
        and "event_id" in {column.name for column in constraint.columns}
        for constraint in reception.constraints
    )
    assert any(
        isinstance(constraint, ForeignKeyConstraint)
        and [element.parent.name for element in constraint.elements]
        == ["event_id", "corporate_id", "store_id", "id"]
        and constraint.referred_table is event
        for constraint in reception.constraints
    )


def test_tc45_58_Eventと種別がpayloadと検索列を保持する() -> None:
    definition = schema.metadata.tables.get("event_definitions")
    event = schema.metadata.tables.get("care_events")
    assert definition is not None, "Event種別テーブルが未定義"
    assert event is not None, "Eventテーブルが未定義"
    for table in (definition, event):
        assert {"payload", "version", "corporate_id"} <= set(table.c.keys())


def test_tc45_07_種別一覧は標準と自法人の行だけを読む() -> None:
    table = schema.metadata.tables.get("event_definitions")
    assert table is not None, "Event種別の読取対象テーブルが未定義"

    compiled = _compiled(table, select(table))

    assert "event_definitions.corporate_id IS NULL" in compiled
    assert "event_definitions.corporate_id = " in compiled


def test_tc45_19_Event一覧は法人と許可店舗の両方で絞られる() -> None:
    table = schema.metadata.tables.get("care_events")
    assert table is not None, "Event読取対象テーブルが未定義"

    compiled = _compiled(table, select(table))

    assert "care_events.corporate_id = " in compiled
    assert "care_events.store_id IN " in compiled
