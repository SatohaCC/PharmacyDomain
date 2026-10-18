"""storeの業務例外。"""

from __future__ import annotations

from app.domain.foundation.exceptions import DomainError


class StoreDomainError(DomainError):
    """店舗ドメインの基底例外"""

    default_message = "店舗ドメインでエラーが発生しました。"
    default_code = "STORE_DOMAIN_ERROR"


class StoreStateConflictError(DomainError):
    """店舗の現在状態と要求された業務が競合する。"""

    default_code = "STORE_STATE_CONFLICT"


class ManagerAssignmentStateConflictError(DomainError):
    """任命の現在状態と要求された操作が競合する。

    基底の ``DomainError`` を直接送出すると、``errors.py`` の対応表で個別に
    扱えず、クライアントは開始済み任命の取消も期間の延長も同じ符号で受け取る。
    """

    default_code = "MANAGER_ASSIGNMENT_STATE_CONFLICT"


class ManagerAbsenceConflictError(DomainError):
    """管理薬剤師が在任していない店舗で、新しい業務を始めようとした。

    店舗状態の競合（``StoreStateConflictError``）とは別の符号にする。休止中の
    店舗と管理薬剤師のいない店舗では、利用者が次に取る手段が違う（前者は店舗を
    再開する、後者は任命する）ので、同じ符号へ畳むと分岐を書けない。
    """

    default_code = "MANAGER_ABSENCE_CONFLICT"


class ManagerPersonUnresolvedError(DomainError):
    """任命しようとしたスタッフに、本人が固定されていない。

    専任義務は自然人にかかるので、本人の分からないスタッフを任命すると、その
    1件だけが兼務の検査をすり抜ける。「分からないなら通す」に倒さない。
    """

    default_code = "MANAGER_PERSON_UNRESOLVED"


class ManagerAssignmentConflictError(DomainError):
    """同店舗または同スタッフの任命期間が重複している。"""

    default_code = "MANAGER_ASSIGNMENT_CONFLICT"


class ManagerExclusiveDutyConflictError(DomainError):
    """同一人物が、同じ期間に複数の薬局の管理薬剤師を兼ねようとしている。

    薬機法第7条第3項は管理薬剤師の専任を求める。競合相手が別法人にありうる
    ため、メッセージには相手の法人も店舗も含めない（テナントを越えて存在を
    知らせることになる）。
    """

    default_code = "MANAGER_EXCLUSIVE_DUTY_CONFLICT"


class StoreNameAlreadyExistsError(StoreDomainError):
    """同一法人内に同名の店舗が既に存在する場合の例外"""

    default_message = "同一法人内に同じ店舗名の店舗が既に登録されています。"
    default_code = "STORE_NAME_ALREADY_EXISTS"


class StoreCodeAlreadyExistsError(StoreDomainError):
    """同一法人内に同一コードの店舗が既に存在する場合の例外"""

    default_message = "同一法人内に同じ店舗コードの店舗が既に登録されています。"
    default_code = "STORE_CODE_ALREADY_EXISTS"


class InsurancePharmacyNumberAlreadyExistsError(StoreDomainError):
    """保険薬局指定番号が既に別店舗で登録されている場合の例外"""

    default_message = "指定された保険薬局指定番号は既に別の店舗で登録されています。"
    default_code = "INSURANCE_PHARMACY_NUMBER_ALREADY_EXISTS"
