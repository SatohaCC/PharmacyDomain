"""Claimコンテキストの識別子・スナップショット用プリミティブ。"""

from __future__ import annotations

import re
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


def _ensure_digits(value: str, *, field_name: str, lengths: tuple[int, ...]) -> None:
    """半角数字かつ規定桁数であることを検証する。

    スナップショットは資格台帳の値をコピーするだけだが、桁数の検証を台帳側だけに
    置くと :class:`CoverageSnapshotBoundary` の実装が不正値を組み立てられてしまう。
    凍結される側にも同じ不変条件を持たせ、請求時点で確実に弾く。
    """
    pattern = "|".join(f"[0-9]{{{length}}}" for length in lengths)
    if not re.fullmatch(pattern, value):
        expected = "桁または".join(str(length) for length in lengths)
        raise DomainValidationError(
            f"{field_name}は半角数字{expected}桁で指定してください。"
        )


class ClaimCoverageCode(BaseNormalizedString):
    """請求時点で固定する被保険者番号など、桁数規定のない符号。"""


class ClaimInsurerNumber(BaseNormalizedString):
    """請求時点で固定する保険者番号。半角数字6桁または8桁。"""

    def validate(self) -> None:
        super().validate()
        _ensure_digits(self.value, field_name="保険者番号", lengths=(6, 8))


class ClaimPublicPayerNumber(BaseNormalizedString):
    """請求時点で固定する公費負担者番号。半角数字8桁。"""

    def validate(self) -> None:
        super().validate()
        _ensure_digits(self.value, field_name="公費負担者番号", lengths=(8,))


class ClaimPublicRecipientNumber(BaseNormalizedString):
    """請求時点で固定する公費受給者番号。半角数字7桁。"""

    def validate(self) -> None:
        super().validate()
        _ensure_digits(self.value, field_name="公費受給者番号", lengths=(7,))


class ClaimCoverageSymbol(BaseNormalizedString):
    """請求時点で固定する被保険者記号。"""


class ClaimCoverageBranchNumber(BaseNormalizedString):
    """請求時点で固定する被保険者番号の枝番。半角数字2桁。"""

    def validate(self) -> None:
        super().validate()
        _ensure_digits(self.value, field_name="枝番", lengths=(2,))


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

    def __post_init__(self) -> None:
        """基底クラスの同値判定に関係なく、正規化後の値を保持する。"""
        normalized = self._normalize(self.value)
        object.__setattr__(self, "value", normalized)
        self.validate()

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
