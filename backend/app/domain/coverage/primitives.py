"""coverageの単一値と列挙・検証規則。"""

from __future__ import annotations

from collections.abc import Sequence
from enum import Enum, StrEnum, auto

from app.domain.foundation.exceptions import DomainValidationError
from app.domain.foundation.primitives.primitives import (
    BaseAwareTimestamp,
    BaseDate,
    BaseNonNegativeInt,
    BaseNormalizedString,
    BasePositiveInt,
    ensure_digits,
)


class CoverageType(StrEnum):
    """患者資格の制度種別。"""

    INSURANCE = "insurance"
    PUBLIC_EXPENSE = "public_expense"


class CoverageInsuredType(StrEnum):
    """保険資格における本人・家族区分。"""

    SELF = "self"
    FAMILY = "family"


class CoverageCode(BaseNormalizedString):
    """被保険者番号など、桁数が規定されていない保険・公費の符号。"""


class InsurerNumber(BaseNormalizedString):
    """保険者番号。国民健康保険は6桁、被用者保険は8桁の半角数字。"""

    def validate(self) -> None:
        super().validate()
        ensure_digits(self.value, field_name="保険者番号", lengths=(6, 8))


class CoverageSymbol(BaseNormalizedString):
    """被保険者記号。桁数の規定はなく、空でないことだけを要求する。"""


class CoverageBranchNumber(BaseNormalizedString):
    """被保険者番号の枝番。半角数字2桁。"""

    def validate(self) -> None:
        super().validate()
        ensure_digits(self.value, field_name="枝番", lengths=(2,))


class CoveragePriority(BasePositiveInt):
    """同時に適用する資格の優先順位。1が最優先で第四順位まで。"""

    def validate(self) -> None:
        super().validate()
        if self.value > 4:
            raise DomainValidationError("適用順位は1から4で指定してください。")


class CoverageBenefitRatio(BaseNonNegativeInt):
    """医療費の給付割合（百分率）。"""

    def validate(self) -> None:
        super().validate()
        if self.value > 100:
            raise DomainValidationError("給付割合は100以下で指定してください。")


class PublicPayerNumber(BaseNormalizedString):
    """公費負担者番号。半角数字8桁。"""

    def validate(self) -> None:
        super().validate()
        ensure_digits(self.value, field_name="公費負担者番号", lengths=(8,))


class PublicRecipientNumber(BaseNormalizedString):
    """公費受給者番号。半角数字7桁。"""

    def validate(self) -> None:
        super().validate()
        ensure_digits(self.value, field_name="公費受給者番号", lengths=(7,))


class CoverageAppliedOn(BaseDate):
    """資格を適用する業務日。"""


class CoverageRecordedAt(BaseAwareTimestamp):
    """資格選択を記録したUTC時刻。"""


class OperatorPrincipalId(BaseNormalizedString):
    """認証基盤が確定した記録者の主体ID。"""


class CoverageValidFrom(BaseDate):
    """患者資格の適用開始日。"""


class CoverageValidTo(BaseDate):
    """患者資格の適用終了日。"""


class CoverageActivatedOn(BaseDate):
    """患者資格台帳行の有効化発効日。"""


class CoverageDeactivatedOn(BaseDate):
    """患者資格台帳行の無効化発効日。この日自体は有効区間に含まない。"""


class PriorityViolation(Enum):
    """順位列の違反種別。"""

    #: 指定できる件数の上限を超えている。
    EXCEEDS_MAXIMUM = auto()
    #: 同じ順位が複数回指定されている。
    DUPLICATED = auto()
    #: 第一順位から連続していない（欠番がある）。
    NOT_CONSECUTIVE = auto()


def find_priority_violation(
    priorities: Sequence[int], *, maximum: int
) -> PriorityViolation | None:
    """順位列が第一順位から重複なく連続しているかを検証する。

    電子レセプトの公費欄は第一公費から順に埋める。第一公費が空で第三公費だけを
    持つ組み合わせは提出時に返戻されるため、欠番を違反として扱う。

    Args:
        priorities: 検証する順位の列。並び順は問わない。
        maximum: 指定できる件数の上限。

    Returns:
        違反があればその種別、なければ ``None``。
    """
    if len(priorities) > maximum:
        return PriorityViolation.EXCEEDS_MAXIMUM
    if len(priorities) != len(set(priorities)):
        return PriorityViolation.DUPLICATED
    if sorted(priorities) != list(range(1, len(priorities) + 1)):
        return PriorityViolation.NOT_CONSECUTIVE
    return None


def public_expenses_are_ordered(priorities: Sequence[int]) -> bool:
    """公費枠が適用順位の昇順で明示されているかを判定する。"""
    return list(priorities) == sorted(priorities)
