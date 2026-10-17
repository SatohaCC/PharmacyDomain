"""Receptionドメインの業務例外。"""

from app.domain.foundation.exceptions import DomainError


class ReceptionDomainError(DomainError):
    """Receptionドメインの基底例外。"""

    default_message = "受付ドメインでエラーが発生しました。"
    default_code = "RECEPTION_DOMAIN_ERROR"


class CoverageSelectionInvalidError(ReceptionDomainError):
    """受付で選択した資格の構成が不正な場合の例外。"""

    default_message = "適用資格選択の構成が不正です。"
    default_code = "COVERAGE_SELECTION_INVALID"


class ReceptionEventAlreadyAssociatedError(ReceptionDomainError):
    """受付に別のEventがすでに関連付いている場合の例外。"""

    default_message = "受付にはすでに別のEventが関連付いています。"
    default_code = "RECEPTION_EVENT_ALREADY_ASSOCIATED"
