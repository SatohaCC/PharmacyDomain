"""Applicationのpaginationを定義する。"""

from __future__ import annotations

from dataclasses import dataclass

MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 50


@dataclass(frozen=True, kw_only=True)
class Page[ItemT]:
    """一覧の1ページ分と、続きを引くためのカーソル。

    ``dict[str, object]`` で返すと、項目名も要素の型も呼び出し側に伝わらず、
    OpenAPI にも自由形式のオブジェクトとしてしか載らない。生成したクライアントは
    一覧の中身を型として扱えなくなる。

    ``next_cursor`` が ``None`` なら続きは無い。
    """

    items: tuple[ItemT, ...]
    next_cursor: str | None = None
