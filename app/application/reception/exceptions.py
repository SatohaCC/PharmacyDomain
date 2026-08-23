"""ReceptionコンテキストのApplication例外。"""

from app.base.application.exceptions import ApplicationError


class ReceptionApplicationError(ApplicationError):
    """Receptionユースケースの基底例外。"""

    default_message = "受付処理中にエラーが発生しました。"
    default_code = "RECEPTION_APPLICATION_ERROR"


class ReceptionStoreNotFoundError(ReceptionApplicationError):
    """対象店舗が存在しない、または法人が異なる場合の例外。"""

    default_message = "受付の対象店舗が見つかりません。"
    default_code = "RECEPTION_STORE_NOT_FOUND"


class ReceptionPatientNotFoundError(ReceptionApplicationError):
    """対象患者が存在しない、または法人が異なる場合の例外。"""

    default_message = "受付の対象患者が見つかりません。"
    default_code = "RECEPTION_PATIENT_NOT_FOUND"


class ReceptionCoverageSelectionError(ReceptionApplicationError):
    """指定資格から有効な選択を構成できない場合の例外。"""

    default_message = "適用資格の選択を構成できません。"
    default_code = "RECEPTION_COVERAGE_SELECTION_ERROR"
