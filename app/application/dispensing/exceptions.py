"""DispensingコンテキストのApplication例外。"""

from app.base.application.exceptions import ApplicationError


class DispensingApplicationError(ApplicationError):
    """調剤ユースケースの基底例外。"""

    default_message = "調剤の処理中にエラーが発生しました。"
    default_code = "DISPENSING_APPLICATION_ERROR"


class DispensingNotFoundError(DispensingApplicationError):
    """対象の調剤セッションが存在しない、または法人が異なる場合の例外。"""

    default_message = "対象の調剤セッションが見つかりません。"
    default_code = "DISPENSING_NOT_FOUND"


class DispensingStoreNotFoundError(DispensingApplicationError):
    """調剤を行う店舗が存在しない、または法人が異なる場合の例外。"""

    default_message = "調剤の対象店舗が見つかりません。"
    default_code = "DISPENSING_STORE_NOT_FOUND"


class DispensingPrescriptionNotFoundError(DispensingApplicationError):
    """対象の処方箋が存在しない、または法人が異なる場合の例外。"""

    default_message = "調剤の対象処方箋が見つかりません。"
    default_code = "DISPENSING_PRESCRIPTION_NOT_FOUND"


class DispensingStaffNotFoundError(DispensingApplicationError):
    """調剤者・鑑査者が存在しない、または法人が異なる場合の例外。

    別法人のスタッフを指定した場合もこの例外に畳む。``AuthorizationError``
    へ分けると、他法人にそのスタッフIDが在ることが呼び出し元へ漏れる。
    """

    default_message = "調剤の担当スタッフが見つかりません。"
    default_code = "DISPENSING_STAFF_NOT_FOUND"


class PrescriptionNotReadyForDispensingError(DispensingApplicationError):
    """処方内容が確定していない処方箋を調剤しようとした場合の例外。

    未回答の疑義照会があるうちは処方内容が確定していない。処方箋側の状態
    （``READY_FOR_DISPENSING``）を確認せずに調剤を始めると、照会中の処方で
    調剤録が作られる。
    """

    default_message = (
        "処方内容が確定していないため、調剤を開始できません"
        "（処方箋を調剤可能な状態にしてください）。"
    )
    default_code = "DISPENSING_PRESCRIPTION_NOT_READY"
