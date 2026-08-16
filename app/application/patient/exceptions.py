"""患者アプリケーション層（ユースケース）の例外定義。"""

from app.base.application.exceptions import ApplicationError


class PatientApplicationError(ApplicationError):
    """患者ユースケースの基底例外。"""

    default_message = "患者の処理中にエラーが発生しました。"
    default_code = "PATIENT_APPLICATION_ERROR"


class PatientNotFoundError(PatientApplicationError):
    """患者が存在しない、または所属法人が異なる場合の例外（HTTP 404相当）。"""

    default_message = "指定された患者が見つかりません。"
    default_code = "PATIENT_NOT_FOUND"
