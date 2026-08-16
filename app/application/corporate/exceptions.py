"""法人コンテキストのアプリケーション例外。"""

from app.base.application.exceptions import ApplicationError, NotFoundError


class CorporateApplicationError(ApplicationError):
    """未検出を除く法人操作の業務エラー（主に409系）の基底。"""

    default_message = "法人の処理中にエラーが発生しました。"
    default_code = "CORPORATE_APPLICATION_ERROR"


class CorporateNotFoundError(NotFoundError):
    """指定された法人が存在しない場合の例外。"""

    default_message = "指定された法人が見つかりません。"
    default_code = "CORPORATE_NOT_FOUND"


class CorporateInactiveError(CorporateApplicationError):
    """対象法人が無効状態で通常操作を受け付けられない場合の例外。"""

    default_message = "対象法人は現在利用できません。"
    default_code = "CORPORATE_INACTIVE"


__all__ = [
    "CorporateApplicationError",
    "CorporateInactiveError",
    "CorporateNotFoundError",
]
