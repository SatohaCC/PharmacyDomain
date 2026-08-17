"""Application層の境界で共有する入力正規化処理（Shared Kernel）。"""

from __future__ import annotations


def to_optional_text(raw: str | None) -> str | None:
    """任意入力の文字列を正規化し、未入力を ``None`` に揃える。

    空文字を「未設定」と読むか「不正な値」と読むかがユースケースごとにぶれると、
    同じ画面から送られた同じ値が登録では通り変更では検証エラーになる。境界で
    1度だけ正規化し、以降は「未設定は ``None`` だけ」という前提で扱えるようにする。

    コンテキストごとに同じ関数を複製すると正規化ルールの変更が片方だけに入り、
    同じ空文字が店舗では項目解除・資格では検証エラーという分岐を生む。そのため
    定義はこのShared Kernelに1つだけ置き、各コンテキストの ``support.py`` は
    再エクスポートするだけに留める。

    Args:
        raw: 外部から渡された任意項目の文字列（未入力は ``None`` または空文字）

    Returns:
        str | None: 前後の余白を除いた文字列。空文字・空白のみの場合は ``None``
    """
    if raw is None:
        return None
    return raw.strip() or None
