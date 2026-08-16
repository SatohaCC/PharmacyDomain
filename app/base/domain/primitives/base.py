"""ドメインプリミティブの基底クラス定義。"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class DomainPrimitive[T](ABC):
    """ドメインプリミティブの基底クラス。

    不変性（frozen）と値による等価性を保証し、サブクラスに値の正規化および
    バリデーションルールの実装を委譲する。

    フィールドは ``value`` 1つだけなので ``kw_only`` は指定しない。位置引数の
    取り違えが起こりえない一方、キーワード名の ``value`` はクラス名が既に語って
    いる情報の繰り返しになるため。フィールドが複数になる概念は
    :class:`DomainPrimitive` ではなく Value Object として定義し、そちらは
    ``kw_only=True`` で同型フィールドの取り違えを防ぐ。
    """

    value: T

    def __post_init__(self) -> None:
        """データクラスの初期化後に正規化とバリデーションを順に実行する。"""
        normalized = self._normalize(self.value)
        if normalized != self.value or type(normalized) is not type(self.value):
            object.__setattr__(self, "value", normalized)
        self.validate()

    def _normalize(self, value: T) -> T:
        """派生クラスで必要に応じてオーバーライドする値の正規化フック。

        デフォルトでは変換を行わずにそのまま返す。
        """
        return value

    @abstractmethod
    def validate(self) -> None:
        """業務ルールの検証ロジック。サブクラスで必ず実装する。"""

    def __str__(self) -> str:
        """文字列表現を返す。"""
        return str(self.value)
