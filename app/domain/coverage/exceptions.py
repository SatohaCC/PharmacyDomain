"""Coverageドメインの業務例外。"""

from app.base.domain.exceptions import DomainError


class CoverageDomainError(DomainError):
    """Coverageドメインの基底例外。"""

    default_message = "患者資格ドメインでエラーが発生しました。"
    default_code = "COVERAGE_DOMAIN_ERROR"


class CoveragePeriodConflictError(CoverageDomainError):
    """同じ制度・優先順位の適用期間が重複している場合の例外。"""

    default_message = "同じ制度・優先順位の患者資格期間が重複しています。"
    default_code = "COVERAGE_PERIOD_CONFLICT"


class CoverageDetailsMismatchError(CoverageDomainError):
    """資格種別と制度別詳細の組み合わせが一致しない場合の例外。"""

    default_message = "患者資格の種別と詳細が一致していません。"
    default_code = "COVERAGE_DETAILS_MISMATCH"


class InsuranceCoveragePriorityError(CoverageDomainError):
    """医療保険に公費の順位を設定した場合の例外。"""

    default_message = "医療保険の適用順位は1で指定してください。"
    default_code = "INSURANCE_COVERAGE_PRIORITY_INVALID"


class CoverageDeactivationAlreadyFixedError(CoverageDomainError):
    """確定済みの無効化発効日を別の日へ変更しようとした場合の例外。"""

    default_message = "患者資格の無効化発効日はすでに確定しています。"
    default_code = "COVERAGE_DEACTIVATION_ALREADY_FIXED"


class CoverageCombinationError(CoverageDomainError):
    """適用資格の組み合わせが成立しない場合の例外。"""

    default_message = "適用資格の組み合わせが不正です。"
    default_code = "COVERAGE_COMBINATION_INVALID"
