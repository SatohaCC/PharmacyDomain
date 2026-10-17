"""HTTP 境界そのもので発生する例外。

認証はApplication層より外側の関心事なので、``ApplicationError`` を継承しない。
Application層に401を持ち込むと、信頼済み ``ActorContext`` を前提に組み立てた
ユースケースが「主体が誰か分からない」状態も扱えることになってしまう。
"""

from __future__ import annotations


class PresentationError(Exception):
    """HTTP 境界から発生する例外の基底クラス。

    ``message`` と ``code`` を持つ形をDomain / Application層の基底例外と揃える。
    応答本文の組み立てが例外の出どころごとに分岐しなくなる。
    """

    default_message: str = "リクエストを処理できませんでした。"
    default_code: str = "PRESENTATION_ERROR"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
    ) -> None:
        """任意のカスタムメッセージ・エラーコードを指定して例外を初期化する。"""
        resolved_message = message if message is not None else self.default_message
        super().__init__(resolved_message)
        self.message = resolved_message
        self.code = code if code is not None else self.default_code

    def __str__(self) -> str:
        return self.message


class AuthenticationError(PresentationError):
    """資格情報を検証できず、操作主体を特定できない（HTTP 401 相当）。

    「権限が無い」（403）とは別物である。403は主体が判明したうえでの拒否であり、
    401は主体がまだ決まっていない。両者を混ぜると、認証基盤が未接続なだけの
    状態が「権限不足」に見えて原因究明が遅れる。
    """

    default_message = "認証が必要です。"
    default_code = "UNAUTHENTICATED"


__all__ = [
    "AuthenticationError",
    "PresentationError",
]
