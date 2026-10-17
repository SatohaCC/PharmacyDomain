"""件数の多い一覧を、次の続きと一緒に返すための共通の形。"""

from dataclasses import dataclass

#: 一度に返せる件数の上限。これを超える指定は入力エラーにする。
MAX_PAGE_SIZE = 100

#: 件数を指定しなかったときの既定。
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


__all__ = ["DEFAULT_PAGE_SIZE", "MAX_PAGE_SIZE", "Page"]
