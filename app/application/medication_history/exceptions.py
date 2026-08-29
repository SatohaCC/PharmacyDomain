"""MedicationHistoryコンテキストのApplication例外。"""

from app.base.application.exceptions import ApplicationError


class MedicationHistoryApplicationError(ApplicationError):
    """薬歴ユースケースの基底例外。"""

    default_message = "薬歴の処理中にエラーが発生しました。"
    default_code = "MEDICATION_HISTORY_APPLICATION_ERROR"


class MedicationHistoryNotFoundError(MedicationHistoryApplicationError):
    """対象の薬歴が存在しない、または法人が異なる場合の例外。"""

    default_message = "対象の薬歴が見つかりません。"
    default_code = "MEDICATION_HISTORY_NOT_FOUND"


class MedicationHistoryStoreNotFoundError(MedicationHistoryApplicationError):
    """服薬指導を行った店舗が存在しない、または法人が異なる場合の例外。"""

    default_message = "薬歴の対象店舗が見つかりません。"
    default_code = "MEDICATION_HISTORY_STORE_NOT_FOUND"


class MedicationHistoryDispensingNotFoundError(MedicationHistoryApplicationError):
    """対象の調剤セッションが存在しない、または法人が異なる場合の例外。"""

    default_message = "薬歴の対象となる調剤セッションが見つかりません。"
    default_code = "MEDICATION_HISTORY_DISPENSING_NOT_FOUND"


class MedicationHistoryStaffNotFoundError(MedicationHistoryApplicationError):
    """指導薬剤師が存在しない、または法人が異なる場合の例外。

    別法人のスタッフを指定した場合もこの例外に畳む。``AuthorizationError``
    へ分けると、他法人にそのスタッフIDが在ることが呼び出し元へ漏れる。
    """

    default_message = "服薬指導を行ったスタッフが見つかりません。"
    default_code = "MEDICATION_HISTORY_STAFF_NOT_FOUND"


class PatientMedicalProfileNotFoundError(MedicationHistoryApplicationError):
    """対象患者の頭書きがまだ投影されていない場合の例外。

    参照系でだけ使う。確定処理は頭書きが無ければ空から作って畳み込むので、
    この例外にはならない。
    """

    default_message = "対象患者の頭書きはまだ作成されていません。"
    default_code = "MEDICATION_HISTORY_PROFILE_NOT_FOUND"
