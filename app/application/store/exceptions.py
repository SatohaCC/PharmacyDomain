"""店舗アプリケーション層（ユースケース）の例外定義。"""

from app.application.common.exceptions import ApplicationError


class StoreApplicationError(ApplicationError):
    """店舗ユースケースの基底例外"""

    default_message = "店舗の処理中にエラーが発生しました。"
    default_code = "STORE_APPLICATION_ERROR"


class StoreNotFoundError(StoreApplicationError):
    """指定された店舗が存在しない、または所属法人が異なる場合の例外（HTTP 404相当）"""

    default_message = "指定された店舗が見つかりません。"
    default_code = "STORE_NOT_FOUND"
