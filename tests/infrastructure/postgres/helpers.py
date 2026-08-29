"""PostgreSQLアダプタのテストで使う組み立て補助。"""

from __future__ import annotations

import importlib
import pkgutil
from typing import Any, cast

from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Dialect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.sql import ClauseElement

import migrations.versions
from app.domain.corporate.corporate import Corporate
from app.domain.corporate.primitives import (
    CorporateName,
    CorporateRepresentativeName,
)
from app.domain.shared.person_name import PersonNamePart
from app.infrastructure.postgres.unit_of_work import PostgresUnitOfWork
from tests.fakes.recording_async_session import FakeResult, RecordingAsyncSession

_MIGRATIONS_PACKAGE = "migrations.versions"


def ordered_migrations() -> list[Any]:
    """``down_revision`` の連鎖をたどって、マイグレーションを適用順に並べる。

    ファイル名の昇順に頼ると、採番規則を変えた瞬間に順序が狂う。
    """
    modules: dict[str, Any] = {}
    for module_info in pkgutil.iter_modules(migrations.versions.__path__):
        module = importlib.import_module(f"{_MIGRATIONS_PACKAGE}.{module_info.name}")
        if hasattr(module, "revision") and hasattr(module, "upgrade"):
            modules[str(module.revision)] = module

    by_parent = {
        (None if module.down_revision is None else str(module.down_revision)): module
        for module in modules.values()
    }
    ordered: list[Any] = []
    parent: str | None = None
    while parent in by_parent:
        current = by_parent[parent]
        ordered.append(current)
        parent = str(current.revision)
    if len(ordered) != len(modules):
        raise AssertionError(
            f"マイグレーションの連鎖が途切れています: 全{len(modules)}件中{len(ordered)}件しか辿れません。"
        )
    return ordered


def create_corporate(name: str = "テスト薬局グループ") -> Corporate:
    """テスト用の法人を1件作る。"""
    return Corporate.create(
        name=CorporateName(name),
        representative_name=CorporateRepresentativeName(
            last_name=PersonNamePart("山田"),
            first_name=PersonNamePart("太郎"),
        ),
    )


def create_unit_of_work(
    session: RecordingAsyncSession,
) -> PostgresUnitOfWork:
    """記録用セッションを返す Unit of Work を作る。"""
    return PostgresUnitOfWork(cast(async_sessionmaker[AsyncSession], lambda: session))


def postgres_dialect() -> Dialect:
    """PostgreSQL方言を返す。

    SQLAlchemyの ``postgresql.dialect`` は動的に束ねられた別名で型注釈が無く、
    strict設定では呼び出しごとに未型付け呼び出しとして扱われる。包み直して
    「型を諦める箇所」を1つに閉じ込める。
    """
    return postgresql.dialect()  # type: ignore[no-untyped-call]


def compiled_sql(statement: ClauseElement) -> str:
    """statement を PostgreSQL 方言のSQL文字列へ変換する。"""
    return str(statement.compile(dialect=postgres_dialect()))


def compiled_params(statement: ClauseElement) -> dict[str, object]:
    """statement に束縛された値を返す。"""
    return dict(statement.compile(dialect=postgres_dialect()).params)


class FakeAsyncpgError(Exception):
    """asyncpg が送出する例外のダブル。

    実物は ``constraint_name`` を**自分の属性として**持つ。psycopg2 の ``diag``
    は asyncpg には無い。ここを実物と違う形にすると、DBなしのテストだけが通って
    実DBで制約名を取り落とす。
    """

    def __init__(self, constraint_name: str) -> None:
        super().__init__(f'制約 "{constraint_name}" に違反しました')
        self.constraint_name = constraint_name


def integrity_error(constraint_name: str) -> IntegrityError:
    """指定した制約名で失敗した IntegrityError を、実物と同じ連鎖で組み立てる。

    SQLAlchemy は asyncpg の例外をDBAPI互換のラッパへ翻訳して ``orig`` に入れ、
    翻訳前の例外を ``__cause__`` に残す。制約名はその奥にしか無い。
    """
    translated = Exception(f'制約 "{constraint_name}" に違反しました')
    translated.__cause__ = FakeAsyncpgError(constraint_name)
    return IntegrityError("INSERT ...", {}, translated)


__all__ = [
    "FakeResult",
    "RecordingAsyncSession",
    "compiled_params",
    "compiled_sql",
    "create_corporate",
    "create_unit_of_work",
    "integrity_error",
    "ordered_migrations",
    "postgres_dialect",
]
