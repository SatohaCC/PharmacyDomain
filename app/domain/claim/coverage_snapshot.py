"""請求・調剤時点で固定する保険・公費スナップショット。"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.claim.exceptions import CoverageCombinationInvalidError
from app.domain.claim.primitives import (
    ClaimCoverageBenefitRatio,
    ClaimCoverageBranchNumber,
    ClaimCoverageCode,
    ClaimCoverageInsuredType,
    ClaimCoveragePriority,
    ClaimCoverageSymbol,
)


@dataclass(frozen=True, kw_only=True)
class InsuranceCoverageSnapshot:
    """請求時点の医療保険資格を値として固定したもの。"""

    insurer_number: ClaimCoverageCode
    insured_symbol: ClaimCoverageSymbol
    insured_number: ClaimCoverageCode
    insured_type: ClaimCoverageInsuredType
    branch_number: ClaimCoverageBranchNumber | None = None
    benefit_ratio: ClaimCoverageBenefitRatio | None = None


@dataclass(frozen=True, kw_only=True)
class PublicExpenseCoverageSnapshot:
    """請求時点の一つの公費資格を値として固定したもの。"""

    priority: ClaimCoveragePriority
    payer_number: ClaimCoverageCode
    recipient_number: ClaimCoverageCode


@dataclass(frozen=True, kw_only=True)
class CoverageSnapshot:
    """請求時点で適用した保険・公費の組み合わせ。"""

    insurance: InsuranceCoverageSnapshot | None = None
    public_expenses: tuple[PublicExpenseCoverageSnapshot, ...] = ()

    def __post_init__(self) -> None:
        """保険・公費の件数と順位を検証し、順位順へ正規化する。"""
        public_expenses = tuple(self.public_expenses)
        if self.insurance is None and not public_expenses:
            raise CoverageCombinationInvalidError(
                "保険または公費を1件以上指定してください。"
            )
        if len(public_expenses) > 4:
            raise CoverageCombinationInvalidError("公費は第四公費まで指定できます。")

        priorities = [item.priority.value for item in public_expenses]
        if len(priorities) != len(set(priorities)):
            raise CoverageCombinationInvalidError(
                "公費の適用順位は重複して指定できません。"
            )

        ordered = tuple(sorted(public_expenses, key=lambda item: item.priority.value))
        if ordered != self.public_expenses:
            object.__setattr__(self, "public_expenses", ordered)
