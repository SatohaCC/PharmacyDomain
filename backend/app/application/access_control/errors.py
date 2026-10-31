"""Applicationのerrorsを定義する。"""

from __future__ import annotations

from app.application.common.exceptions import ApplicationError, NotFoundError


class TenantBoundaryNotFoundError(NotFoundError):
    """別法人の存在を漏らさないために返す404相当の例外。

    Note:
        通常のリソース未検出（NotFoundError）とクライアント側で完全に同一に
        見せる必要があるため、既定メッセージとエラーコードを親クラスと意図的に
        同一値としています。
    """

    default_message = "指定されたリソースが見つかりません。"
    default_code = "RESOURCE_NOT_FOUND"


class StoreContextRequiredError(ApplicationError):
    """店舗業務の実行時に作業店舗が選択されていないことを表す409相当の例外。"""

    default_message = "店舗業務を行うには作業対象の店舗を選択してください。"
    default_code = "STORE_CONTEXT_REQUIRED"
