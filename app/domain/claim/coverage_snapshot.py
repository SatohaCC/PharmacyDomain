"""請求・調剤時点で固定する保険・公費スナップショット。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar

from app.base.domain.value_object import ValueObject
from app.domain.claim.exceptions import CoverageCombinationInvalidError
from app.domain.claim.primitives import (
    ClaimCoverageBenefitRatio,
    ClaimCoverageBranchNumber,
    ClaimCoverageCode,
    ClaimCoverageInsuredType,
    ClaimCoveragePriority,
    ClaimCoverageSymbol,
    ClaimInsurerNumber,
    ClaimPublicPayerNumber,
    ClaimPublicRecipientNumber,
)


@dataclass(frozen=True, kw_only=True)
class InsuranceCoverageSnapshot(ValueObject):
    """請求時点の医療保険資格を値として固定したもの。

    ``benefit_ratio`` は患者負担額を決める値であり、スナップショットが存在する
    目的そのものなので任意項目にしない。資格台帳の
    :class:`InsuranceCoverageDetails` でも必須であり、両者で必須性を揃える。
    """

    insurer_number: ClaimInsurerNumber
    insured_symbol: ClaimCoverageSymbol
    insured_number: ClaimCoverageCode
    insured_type: ClaimCoverageInsuredType
    benefit_ratio: ClaimCoverageBenefitRatio
    branch_number: ClaimCoverageBranchNumber | None = None

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "insurer_number": "保険者番号",
        "insured_symbol": "被保険者記号",
        "insured_number": "被保険者番号",
        "insured_type": "本人・家族区分",
        "benefit_ratio": "給付割合",
        "branch_number": "枝番",
    }


@dataclass(frozen=True, kw_only=True)
class PublicExpenseCoverageSnapshot(ValueObject):
    """請求時点の一つの公費資格を値として固定したもの。"""

    priority: ClaimCoveragePriority
    payer_number: ClaimPublicPayerNumber
    recipient_number: ClaimPublicRecipientNumber

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "priority": "公費適用順位",
        "payer_number": "公費負担者番号",
        "recipient_number": "公費受給者番号",
    }


@dataclass(frozen=True, kw_only=True)
class CoverageSnapshot(ValueObject):
    """請求時点で適用した保険・公費の組み合わせ。"""

    insurance: InsuranceCoverageSnapshot | None = None
    public_expenses: tuple[PublicExpenseCoverageSnapshot, ...] = ()

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "insurance": "医療保険スナップショット",
        "public_expenses": "公費スナップショット",
    }

    def _normalize_fields(self) -> None:
        """公費スナップショットを順位順へ正規化する。"""
        if not isinstance(self.public_expenses, tuple) or not all(
            isinstance(item, PublicExpenseCoverageSnapshot)
            for item in self.public_expenses
        ):
            return
        public_expenses = self.public_expenses
        ordered = tuple(sorted(public_expenses, key=lambda item: item.priority.value))
        object.__setattr__(self, "public_expenses", ordered)

    def validate(self) -> None:
        """保険・公費の件数と公費順位を検証する。"""
        public_expenses = self.public_expenses
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
        # 電子レセプトの公費欄は第一公費から順に埋める。第一公費が空で第三公費
        # だけを持つ組み合わせは提出時に返戻されるため、1から連続していることを
        # 凍結前に検証する。
        if sorted(priorities) != list(range(1, len(priorities) + 1)):
            raise CoverageCombinationInvalidError(
                "公費の適用順位は第一公費から連続して指定してください。"
            )
