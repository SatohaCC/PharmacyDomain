"""PostgreSQL 制約違反を Domain 例外へ写像する補助関数。"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy.exc import IntegrityError

# 例外連鎖のうち、SQLAlchemy と DBAPI ラッパが明示的に張るリンクだけを辿る。
# ``__context__`` は「処理中に別の例外が起きた」だけの無関係な例外も繋ぐため、
# 別の制約名を拾ってしまう危険がある。
_LINK_ATTRIBUTES = ("orig", "__cause__")


def constraint_name(error: IntegrityError) -> str | None:
    """違反した制約の名前を取り出す。

    asyncpg の例外は SQLAlchemy が DBAPI 互換のラッパへ翻訳して ``orig`` に入れる。
    そのラッパは ``sqlstate`` しか持たず、サーバが返した制約名は翻訳前の元例外
    （``__cause__``）の ``constraint_name`` にだけ残る。psycopg2 の ``diag`` は
    asyncpg には存在しないので、例外連鎖をたどって探す。
    """
    for candidate in _linked_errors(error):
        name = getattr(candidate, "constraint_name", None)
        if isinstance(name, str) and name:
            return name
    return None


def _linked_errors(error: BaseException) -> Iterator[BaseException]:
    """例外連鎖を、同じ例外を二度たどらずに列挙する。"""
    seen: set[int] = set()
    pending: list[BaseException] = [error]
    while pending:
        current = pending.pop(0)
        if id(current) in seen:
            continue
        seen.add(id(current))
        yield current
        for attribute in _LINK_ATTRIBUTES:
            linked = getattr(current, attribute, None)
            if isinstance(linked, BaseException):
                pending.append(linked)
