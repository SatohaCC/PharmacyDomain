"""任意項目のプリミティブ変換を1箇所へ寄せる。

DTOの生成と入力の変換では ``X.value if X is not None else None`` という定型が
項目ごとに繰り返される。1行に収まらず3〜4行へ折り返されるため、DTOのフィールド
構成そのものが定型に埋もれる。さらに悪いことに、意味のある変換（``Decimal`` を
``str`` へ落とす等）と単なる写しが同じ見た目になり、読み手が注目すべき箇所を
見分けられなくなる。ここへ寄せると、残った条件式が「本当に条件のある処理」だけ
になる。

Application共通基盤は標準ライブラリだけに依存させる規則があるため、
``DomainPrimitive`` を直接受けず ``value`` を持つ構造的な型として受ける。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from app.application.common.input_normalization import to_optional_text


class HasValue[T](Protocol):
    """``value`` 1つで値を表すドメインプリミティブの構造的な型。"""

    @property
    def value(self) -> T:
        """保持する値。"""
        ...


def unwrap[T](primitive: HasValue[T] | None) -> T | None:
    """任意項目のプリミティブから素の値を取り出す。未設定なら ``None``。

    Args:
        primitive: 取り出す対象のプリミティブ（未設定は ``None``）

    Returns:
        T | None: プリミティブが保持する値。未設定の場合は ``None``
    """
    return primitive.value if primitive is not None else None


def build_optional[R](raw: str | None, factory: Callable[[str], R]) -> R | None:
    """任意入力の文字列を正規化し、値があるときだけプリミティブを生成する。

    正規化を呼び出し側に委ねない。委ねると、正規化を挟んだ項目と挟まなかった
    項目が混在し、同じ空文字が項目によって「未設定」と「不正な値」に分かれる。

    Args:
        raw: 外部から渡された任意項目の文字列（未入力は ``None`` または空文字）
        factory: 正規化後の文字列からプリミティブを生成する呼び出し可能オブジェクト

    Returns:
        R | None: 生成したプリミティブ。空文字・空白のみ・``None`` の場合は ``None``
    """
    text = to_optional_text(raw)
    return factory(text) if text is not None else None
