"""アプリケーション層の基底例外定義（Shared Kernel）。

ユースケースの実行時に発生するエラー（リソース不在、権限不足など）を扱う。
ドメイン層（業務ルール違反）とは責務を分離し、プレゼンテーション層（Web API）
において HTTP 404 や 403 などのステータスコードへ対応付ける。
"""

from __future__ import annotations


class ApplicationError(Exception):
    """アプリケーション層から発生するすべての例外の基底クラス。"""

    default_message: str = "アプリケーションエラーが発生しました。"
    default_code: str = "APPLICATION_ERROR"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
    ) -> None:
        """カスタムメッセージやエラーコードを指定して例外を初期化する。"""
        resolved_message = message if message is not None else self.default_message
        super().__init__(resolved_message)
        self.message = resolved_message
        self.code = code if code is not None else self.default_code

    def __str__(self) -> str:
        return self.message


class NotFoundError(ApplicationError):
    """要求されたリソースが存在しない場合の基底例外（HTTP 404 相当）。

    Note:
        この基底を採用する404例外が継承する。現在 `CorporateNotFoundError` と
        `TenantBoundaryNotFoundError` のみが継承しており、`StoreNotFoundError` /
        `StaffNotFoundError` は各コンテキストの `XxxApplicationError` を継承する。
        そのため、例外からHTTPステータスを決める処理は `NotFoundError` の捕捉だけでは
        404を網羅できない。
    """

    default_message = "指定されたリソースが見つかりません。"
    default_code = "RESOURCE_NOT_FOUND"


class AuthorizationError(ApplicationError):
    """操作権限がない、またはテナント境界を越えたアクセス時の基底例外（HTTP 403 相当）。"""

    default_message = "この操作を実行する権限がありません。"
    default_code = "FORBIDDEN"
