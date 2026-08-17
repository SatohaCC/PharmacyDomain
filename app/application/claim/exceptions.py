"""ClaimコンテキストのApplication例外。"""

from app.base.application.exceptions import ApplicationError


class ClaimApplicationError(ApplicationError):
    """Claimユースケースの基底例外。"""

    default_message = "請求・調剤履歴の処理中にエラーが発生しました。"
    default_code = "CLAIM_APPLICATION_ERROR"


class CoverageUsageNotFoundError(ClaimApplicationError):
    """適用資格利用履歴が存在しない場合の例外。"""

    default_message = "指定された適用資格利用履歴が見つかりません。"
    default_code = "COVERAGE_USAGE_NOT_FOUND"


class ClaimStoreNotFoundError(ClaimApplicationError):
    """利用履歴の店舗が存在しない、または法人が異なる場合の例外。"""

    default_message = "利用履歴の対象店舗が見つかりません。"
    default_code = "CLAIM_STORE_NOT_FOUND"


class ClaimPatientNotFoundError(ClaimApplicationError):
    """利用履歴の患者が存在しない、または法人が異なる場合の例外。"""

    default_message = "利用履歴の対象患者が見つかりません。"
    default_code = "CLAIM_PATIENT_NOT_FOUND"


class ClaimCoverageSelectionError(ClaimApplicationError):
    """利用資格の選択をスナップショット化できない場合の例外。"""

    default_message = "適用資格の選択をスナップショット化できません。"
    default_code = "CLAIM_COVERAGE_SELECTION_ERROR"
