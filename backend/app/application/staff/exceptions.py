"""スタッフアプリケーション層（ユースケース）の例外定義。"""

from app.application.common.exceptions import ApplicationError


class StaffApplicationError(ApplicationError):
    """スタッフユースケースの基底例外"""

    default_message = "スタッフの処理中にエラーが発生しました。"
    default_code = "STAFF_APPLICATION_ERROR"


class StaffNotFoundError(StaffApplicationError):
    """指定されたスタッフが存在しない、または所属法人が異なる場合の例外（HTTP 404相当）"""

    default_message = "指定されたスタッフが見つかりません。"
    default_code = "STAFF_NOT_FOUND"
