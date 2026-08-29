"""Claimコンテキストの識別子・スナップショット用プリミティブ。"""

from __future__ import annotations

from enum import StrEnum

from app.domain.foundation.exceptions import DomainValidationError
from app.domain.foundation.primitives.primitives import (
    BaseNonNegativeInt,
    BaseNormalizedString,
    BasePositiveInt,
    ensure_digits,
)


class ClaimCoverageCode(BaseNormalizedString):
    """請求時点で固定する被保険者番号など、桁数規定のない符号。"""


class ClaimInsurerNumber(BaseNormalizedString):
    """請求時点で固定する保険者番号。半角数字6桁または8桁。"""

    def validate(self) -> None:
        super().validate()
        ensure_digits(self.value, field_name="保険者番号", lengths=(6, 8))


class ClaimPublicPayerNumber(BaseNormalizedString):
    """請求時点で固定する公費負担者番号。半角数字8桁。"""

    def validate(self) -> None:
        super().validate()
        ensure_digits(self.value, field_name="公費負担者番号", lengths=(8,))


class ClaimPublicRecipientNumber(BaseNormalizedString):
    """請求時点で固定する公費受給者番号。半角数字7桁。"""

    def validate(self) -> None:
        super().validate()
        ensure_digits(self.value, field_name="公費受給者番号", lengths=(7,))


class ClaimCoverageSymbol(BaseNormalizedString):
    """請求時点で固定する被保険者記号。"""


class ClaimCoverageBranchNumber(BaseNormalizedString):
    """請求時点で固定する被保険者番号の枝番。半角数字2桁。"""

    def validate(self) -> None:
        super().validate()
        ensure_digits(self.value, field_name="枝番", lengths=(2,))


class ClaimCoverageInsuredType(StrEnum):
    """請求時点で固定する本人・家族区分。"""

    SELF = "self"
    FAMILY = "family"


class ClaimCoveragePriority(BasePositiveInt):
    """公費の適用順位。第一公費から第四公費までを表す。"""

    def validate(self) -> None:
        super().validate()
        if self.value > 4:
            raise DomainValidationError("公費の適用順位は1から4で指定してください。")


class ClaimCoverageBenefitRatio(BaseNonNegativeInt):
    """スナップショットへ明示された給付割合。"""

    def validate(self) -> None:
        super().validate()
        if self.value > 100:
            raise DomainValidationError("給付割合は100以下で指定してください。")
