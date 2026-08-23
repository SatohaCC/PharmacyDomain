"""Receptionドメインの業務例外。"""

from app.base.domain.exceptions import DomainError


class ReceptionDomainError(DomainError):
    """Receptionドメインの基底例外。"""

    default_message = "受付ドメインでエラーが発生しました。"
    default_code = "RECEPTION_DOMAIN_ERROR"


class CoverageSelectionRecordInvalidError(ReceptionDomainError):
    """適用資格選択履歴の構成が不正な場合の例外。"""

    default_message = "適用資格選択履歴の構成が不正です。"
    default_code = "COVERAGE_SELECTION_RECORD_INVALID"
