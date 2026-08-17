"""患者ドメインの業務例外。"""

from app.base.domain.exceptions import DomainError


class PatientDomainError(DomainError):
    """患者ドメインの基底例外。"""

    default_message = "患者ドメインでエラーが発生しました。"
    default_code = "PATIENT_DOMAIN_ERROR"


class PatientExternalIdentifierAlreadyExistsError(PatientDomainError):
    """連携先と外部患者IDの組が既に登録されている場合の例外。"""

    default_message = "同じ連携先の外部患者IDは既に登録されています。"
    default_code = "PATIENT_EXTERNAL_IDENTIFIER_ALREADY_EXISTS"
