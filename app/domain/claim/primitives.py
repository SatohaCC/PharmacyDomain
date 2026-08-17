"""Claimコンテキストの識別子・スナップショット用プリミティブ。"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from app.base.domain.exceptions import DomainValidationError
from app.base.domain.primitives.base import DomainPrimitive
from app.base.domain.primitives.primitives import (
    BaseNonNegativeInt,
    BaseNormalizedString,
    BasePositiveInt,
    EntityUUID,
)


class ClaimCoverageUsageId(EntityUUID):
    """適用資格利用履歴の一意識別子（UUIDv7）。"""

    identifier_name = "適用資格利用履歴ID"


class ClaimCoverageCode(BaseNormalizedString):
    """請求時点で固定する保険・公費番号。"""


class ClaimCoverageSymbol(BaseNormalizedString):
    """請求時点で固定する被保険者記号。"""


class ClaimCoverageBranchNumber(BaseNormalizedString):
    """請求時点で固定する被保険者番号の枝番。"""


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


class CoverageUsageTimestamp(DomainPrimitive[datetime]):
    """適用資格を利用した日時。UTCのタイムゾーン付き日時へ正規化する。"""

    def _normalize(self, value: datetime) -> datetime:
        if not isinstance(value, datetime):
            raise DomainValidationError(
                "適用資格の利用日時は日時型で指定してください。"
            )
        if value.tzinfo is None or value.utcoffset() is None:
            raise DomainValidationError(
                "適用資格の利用日時はタイムゾーン付きで指定してください。"
            )
        return value.astimezone(UTC)

    def validate(self) -> None:
        if not isinstance(self.value, datetime):
            raise DomainValidationError(
                "適用資格の利用日時は日時型で指定してください。"
            )
