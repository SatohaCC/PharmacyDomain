"""法人ドメイン固有の業務例外定義。"""

from app.base.domain.exceptions import DomainError


class CorporateDomainError(DomainError):
    """法人ドメインの基底例外"""

    default_message = "法人ドメインでエラーが発生しました。"
    default_code = "CORPORATE_DOMAIN_ERROR"


class CorporateNameAlreadyExistsError(CorporateDomainError):
    """同じ法人名を持つ法人が既に登録されている場合の例外"""

    default_message = "同じ法人名の法人が既に登録されています。"
    default_code = "CORPORATE_NAME_ALREADY_EXISTS"
