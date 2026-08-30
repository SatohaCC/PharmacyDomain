"""店舗ドメインにおける業務例外定義。"""

from app.domain.foundation.exceptions import DomainError


class StoreDomainError(DomainError):
    """店舗ドメインの基底例外"""

    default_message = "店舗ドメインでエラーが発生しました。"
    default_code = "STORE_DOMAIN_ERROR"


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
