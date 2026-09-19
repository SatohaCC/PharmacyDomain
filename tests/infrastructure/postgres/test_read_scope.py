"""店舗ロールの読取範囲が、全テーブルに対して宣言されていることを固定する。

以前の読取範囲は「テーブル名と列名のどれにも当たらなければ条件を付けない」
という既定を持っていた。新しいテーブルを足した瞬間に店舗ロールへ全件が見え、
しかもそれを知らせるものが無い。判断を保留できる欄を作らないために、宣言の
網羅と、宣言どおりのSQLになることの両方を検査する。
"""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import MetaData, Select, Table, select

from app.infrastructure.postgres import schema
from app.infrastructure.postgres.read_scope import (
    READ_SCOPE_KINDS,
    ReadScopeKind,
    RepositoryReadScope,
    UnscopedTableError,
)

_CORPORATE_ID = UUID("01890000-0000-7000-8000-000000000000")
_STORE_ID = UUID("01890000-0000-7000-8000-000000000001")
_PERSON_ID = UUID("01890000-0000-7000-8000-0000000000a0")
_ACCOUNT_ID = UUID("01890000-0000-7000-8000-0000000000a1")


def _scope() -> RepositoryReadScope:
    return RepositoryReadScope(
        _CORPORATE_ID,
        (_STORE_ID,),
        date(2026, 9, 17),
        _PERSON_ID,
        _ACCOUNT_ID,
    )


def _compiled(table: Table, statement: Select[Any]) -> str:
    return str(_scope().apply(table, statement).compile())


def test_全てのテーブルに読取範囲が宣言されている() -> None:
    """宣言を忘れたテーブルは、店舗ロールに無条件で見えてしまう。"""
    # Act
    existing = {table.name for table in schema.metadata.sorted_tables}

    # Assert
    assert set(READ_SCOPE_KINDS) == existing, (
        f"未宣言: {sorted(existing - set(READ_SCOPE_KINDS))} / "
        f"実在しない宣言: {sorted(set(READ_SCOPE_KINDS) - existing)}"
    )


def test_宣言していないテーブルは_無条件で読ませない() -> None:
    """既定を「制限しない」に倒すと、追加した当日から漏れる。"""
    # Arrange
    unknown = Table("未宣言テーブル", MetaData())

    # Act & Assert
    with pytest.raises(UnscopedTableError, match="未宣言テーブル"):
        _scope().apply(unknown, select(1))


@pytest.mark.parametrize(
    "table_name",
    sorted(
        name
        for name, kind in READ_SCOPE_KINDS.items()
        if kind is not ReadScopeKind.GLOBAL
    ),
)
def test_非グローバルなテーブルは_必ず条件が付く(table_name: str) -> None:
    """条件が1つも付かない経路が残っていないことを、SQLの形で確かめる。"""
    # Arrange
    table = schema.metadata.tables[table_name]

    # Act
    compiled = _compiled(table, select(table))

    # Assert
    assert "WHERE " in compiled, f"{table_name} に条件が付いていない"


def test_法人内の台帳は_自法人だけに絞られる() -> None:
    # Arrange
    table = schema.metadata.tables["patients"]

    # Act
    compiled = _compiled(table, select(table))

    # Assert
    assert "patients.corporate_id = " in compiled
    assert "store_id" not in compiled


def test_店舗の記録は_法人と許可店舗の両方で絞られる() -> None:
    # Arrange
    table = schema.metadata.tables["prescriptions"]

    # Act
    compiled = _compiled(table, select(table))

    # Assert
    assert "prescriptions.corporate_id = " in compiled
    assert "prescriptions.store_id IN " in compiled


def test_法人表は_自法人の行だけに絞られる() -> None:
    """他法人を読めると、存在が漏れるうえ有効状態まで参照できる。"""
    # Arrange
    table = schema.metadata.tables["corporates"]

    # Act
    compiled = _compiled(table, select(table))

    # Assert
    assert "corporates.id = " in compiled


def test_店舗表は_許可店舗の行だけに絞られる() -> None:
    # Arrange
    table = schema.metadata.tables["stores"]

    # Act
    compiled = _compiled(table, select(table))

    # Assert
    assert "stores.corporate_id = " in compiled
    assert "stores.id IN " in compiled


@pytest.mark.parametrize(
    ("table_name", "column"),
    [
        ("account_people", "account_people.id = "),
        ("user_accounts", "user_accounts.id = "),
    ],
)
def test_本人とアカウントは_自分の行だけに絞られる(
    table_name: str, column: str
) -> None:
    """他人のアカウント行を読めると、本人とアカウントの対応が漏れる。"""
    # Arrange
    table = schema.metadata.tables[table_name]

    # Act
    compiled = _compiled(table, select(table))

    # Assert
    assert column in compiled


def test_スタッフは_適用日の所属で絞られる() -> None:
    """退職者や他店のスタッフを、所属期間を無視して読めてはいけない。"""
    # Arrange
    table = schema.metadata.tables["staff_members"]

    # Act
    compiled = _compiled(table, select(table))

    # Assert
    assert "staff_members.corporate_id = " in compiled
    assert "EXISTS" in compiled
    assert "jsonb_array_elements" in compiled


def test_非テナントの参照マスタには_条件を付けない() -> None:
    """薬価基準は国が定めるので、法人や店舗で内容が変わらない。"""
    # Arrange
    table = schema.metadata.tables["medicines"]

    # Act
    compiled = _compiled(table, select(table))

    # Assert
    assert "WHERE" not in compiled
