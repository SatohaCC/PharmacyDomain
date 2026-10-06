"""適用時点で固定する健康保険・公費負担医療の控えデータ。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar

from app.domain.coverage.exceptions import CoverageCombinationInvalidError
from app.domain.coverage.primitives import (
    CoverageBenefitRatio,
    CoverageBranchNumber,
    CoverageCode,
    CoverageInsuredType,
    CoveragePriority,
    CoverageSymbol,
    InsurerNumber,
    PublicPayerNumber,
    PublicRecipientNumber,
)
from app.domain.coverage.priority_rules import (
    PriorityViolation,
    find_priority_violation,
)
from app.domain.foundation.value_object import ValueObject

#: 公費は第一公費から第四公費までを同時に固定できる。
MAXIMUM_PUBLIC_EXPENSE_COUNT = 4

#: 順位規則の違反種別に対応する日本語メッセージ。規則本体は Coverage の
#: :func:`find_priority_violation` に1つだけあり、文言と例外型だけがここにある。
PUBLIC_EXPENSE_PRIORITY_MESSAGES: Mapping[PriorityViolation, str] = {
    PriorityViolation.EXCEEDS_MAXIMUM: "公費は第四公費まで指定できます。",
    PriorityViolation.DUPLICATED: "公費の適用順位は重複して指定できません。",
    PriorityViolation.NOT_CONSECUTIVE: (
        "公費の適用順位は第一公費から連続して指定してください。"
    ),
}


@dataclass(frozen=True, kw_only=True)
class InsuranceCoverageSnapshot(ValueObject):
    """適用時点の健康保険証情報（保険者番号・記号番号・給付割合等）の控えデータ。

    ``benefit_ratio`` は患者負担額（自己負担割合・給付割合）を決める値であり、
    請求データの整合性を保つ目的そのものなので必須項目です。
    資格台帳の :class:`InsuranceCoverageDetails` と必須性を揃えています。
    """

    insurer_number: InsurerNumber
    insured_symbol: CoverageSymbol
    insured_number: CoverageCode
    insured_type: CoverageInsuredType
    benefit_ratio: CoverageBenefitRatio
    branch_number: CoverageBranchNumber | None = None

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
    """適用時点の公費負担医療（第一〜第四公費）の控えデータ。"""

    priority: CoveragePriority
    payer_number: PublicPayerNumber
    recipient_number: PublicRecipientNumber

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "priority": "公費適用順位",
        "payer_number": "公費負担者番号",
        "recipient_number": "公費受給者番号",
    }


@dataclass(frozen=True, kw_only=True)
class CoverageSnapshot(ValueObject):
    """適用時点で固定した健康保険および公費負担医療の組み合わせ控えデータ。"""

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
        """健康保険および公費の指定件数（1件以上必須）と公費の適用順位（第一〜第四公費の連続性）を検証する。"""
        public_expenses = self.public_expenses
        if self.insurance is None and not public_expenses:
            raise CoverageCombinationInvalidError(
                "保険または公費を1件以上指定してください。"
            )

        violation = find_priority_violation(
            [item.priority.value for item in public_expenses],
            maximum=MAXIMUM_PUBLIC_EXPENSE_COUNT,
        )
        if violation is not None:
            raise CoverageCombinationInvalidError(
                PUBLIC_EXPENSE_PRIORITY_MESSAGES[violation]
            )
