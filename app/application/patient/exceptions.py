"""患者アプリケーション層（ユースケース）の例外定義。"""

from app.application.common.exceptions import ApplicationError


class PatientApplicationError(ApplicationError):
    """患者ユースケースの基底例外。"""

    default_message = "患者の処理中にエラーが発生しました。"
    default_code = "PATIENT_APPLICATION_ERROR"


class PatientNotFoundError(PatientApplicationError):
    """患者が存在しない、または所属法人が異なる場合の例外（HTTP 404相当）。"""

    default_message = "指定された患者が見つかりません。"
    default_code = "PATIENT_NOT_FOUND"


class PatientExternalIdentifierNotFoundError(PatientApplicationError):
    """外部患者IDの対応付けが存在しない、または法人が異なる場合の例外。"""

    default_message = "指定された外部患者IDが見つかりません。"
    default_code = "PATIENT_EXTERNAL_IDENTIFIER_NOT_FOUND"
