"""ドメイン層の例外の基底（Shared Kernel）。

ドメインプリミティブのバリデーション違反は業務例外より内側で発生するため、
ここに置く。プロダクト固有の業務例外は各コンテキストの exceptions が
:class:`DomainError` を継承して定義するので、プレゼンテーション層は
:class:`DomainError` 1つを捕まえれば両方を扱える。
"""

from __future__ import annotations


class DomainError(Exception):
    """ドメイン層から発生するすべての例外の基底クラス。

    HTTP・データベースなど外側のレイヤーに関する知識を持ってはならない。
    """

    default_message: str = "ドメインエラーが発生しました。"
    default_code: str = "DOMAIN_ERROR"

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


class DomainValidationError(DomainError):
    """ドメインプリミティブの制約違反（不正な値でVOを生成しようとした）を表す。"""

    default_message = "ドメインプリミティブに不正な値が指定されました。"
    default_code = "DOMAIN_VALIDATION_ERROR"
