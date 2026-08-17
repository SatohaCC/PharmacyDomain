"""Claimコンテキストのドメイン例外。"""

from app.base.domain.exceptions import DomainError


class ClaimDomainError(DomainError):
    """Claimドメインの基底例外。"""

    default_message = "請求ドメインでエラーが発生しました。"
    default_code = "CLAIM_DOMAIN_ERROR"


class CoverageCombinationInvalidError(ClaimDomainError):
    """請求時に適用する保険・公費の組み合わせが不正な場合の例外。"""

    default_message = "保険・公費の適用組み合わせが不正です。"
    default_code = "COVERAGE_COMBINATION_INVALID"
