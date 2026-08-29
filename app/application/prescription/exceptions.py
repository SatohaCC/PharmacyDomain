"""PrescriptionコンテキストのApplication例外。"""

from app.application.common.exceptions import ApplicationError


class PrescriptionApplicationError(ApplicationError):
    """処方箋ユースケースの基底例外。"""

    default_message = "処方箋の処理中にエラーが発生しました。"
    default_code = "PRESCRIPTION_APPLICATION_ERROR"


class PrescriptionNotFoundError(PrescriptionApplicationError):
    """対象処方箋が存在しない、または法人が異なる場合の例外。"""

    default_message = "対象の処方箋が見つかりません。"
    default_code = "PRESCRIPTION_NOT_FOUND"


class PrescriptionStoreNotFoundError(PrescriptionApplicationError):
    """受付店舗が存在しない、または法人が異なる場合の例外。"""

    default_message = "処方箋の受付店舗が見つかりません。"
    default_code = "PRESCRIPTION_STORE_NOT_FOUND"


class PrescriptionPatientNotFoundError(PrescriptionApplicationError):
    """対象患者が存在しない、または法人が異なる場合の例外。"""

    default_message = "処方箋の対象患者が見つかりません。"
    default_code = "PRESCRIPTION_PATIENT_NOT_FOUND"


class PrescriptionPharmacistNotFoundError(PrescriptionApplicationError):
    """照会実施者が存在しない、または法人が異なる場合の例外。

    別法人のスタッフを指定した場合もこの例外に畳む。``AuthorizationError``
    へ分けると、他法人にそのスタッフIDが在ることが呼び出し元へ漏れる。
    """

    default_message = "疑義照会の実施者が見つかりません。"
    default_code = "PRESCRIPTION_PHARMACIST_NOT_FOUND"


class PrescriptionCoverageSelectionNotFoundError(PrescriptionApplicationError):
    """紐付けた資格選択履歴が存在しない、または法人・患者が異なる場合の例外。"""

    default_message = "処方箋に紐付ける資格選択履歴が見つかりません。"
    default_code = "PRESCRIPTION_COVERAGE_SELECTION_NOT_FOUND"
