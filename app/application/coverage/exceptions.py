"""Coverageアプリケーション層の例外。"""

from app.application.common.exceptions import ApplicationError


class CoverageApplicationError(ApplicationError):
    """Coverageユースケースの基底例外。"""

    default_message = "患者資格の処理中にエラーが発生しました。"
    default_code = "COVERAGE_APPLICATION_ERROR"


class PatientCoverageNotFoundError(CoverageApplicationError):
    """患者資格が存在しない、または法人が異なる場合の例外。"""

    default_message = "指定された患者資格が見つかりません。"
    default_code = "PATIENT_COVERAGE_NOT_FOUND"


class CoveragePatientNotFoundError(CoverageApplicationError):
    """資格を関連付ける患者が存在しない場合の例外。"""

    default_message = "資格を関連付ける患者が見つかりません。"
    default_code = "COVERAGE_PATIENT_NOT_FOUND"
