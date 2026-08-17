"""Coverageコンテキストの識別子・資格情報プリミティブ。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum

from app.base.domain.exceptions import DomainValidationError
from app.base.domain.primitives.primitives import (
    BaseNonNegativeInt,
    BaseNormalizedString,
    BasePositiveInt,
    EntityUUID,
)


class PatientCoverageId(EntityUUID):
    """患者資格の一意識別子（UUIDv7）。"""

    identifier_name = "患者資格ID"


class CoverageType(StrEnum):
    """患者資格の制度種別。"""

    INSURANCE = "insurance"
    PUBLIC_EXPENSE = "public_expense"


class CoverageInsuredType(StrEnum):
    """保険資格における本人・家族区分。"""

    SELF = "self"
    FAMILY = "family"


class CoverageCode(BaseNormalizedString):
    """保険・公費の番号。"""


class CoverageSymbol(BaseNormalizedString):
    """被保険者記号。"""


class CoverageBranchNumber(BaseNormalizedString):
    """被保険者番号の枝番。"""


class CoveragePriority(BasePositiveInt):
    """同時に適用する資格の優先順位。1が最優先。"""


class CoverageBenefitRatio(BaseNonNegativeInt):
    """医療費の給付割合（百分率）。"""

    def validate(self) -> None:
        super().validate()
        if self.value > 100:
            raise DomainValidationError("給付割合は100以下で指定してください。")


class PublicPayerNumber(CoverageCode):
    """公費負担者番号。"""


class PublicRecipientNumber(CoverageCode):
    """公費受給者番号。"""


@dataclass(frozen=True, kw_only=True)
class CoveragePeriod:
    """患者資格の適用期間。終了日なしは現在も有効であることを表す。"""

    valid_from: date
    valid_to: date | None = None

    def __post_init__(self) -> None:
        """日付型と前後関係を検証する。"""
        for field_name, value in (
            ("適用開始日", self.valid_from),
            ("適用終了日", self.valid_to),
        ):
            if value is not None and (
                not isinstance(value, date) or isinstance(value, datetime)
            ):
                raise DomainValidationError(f"{field_name}は日付型で指定してください。")
        if self.valid_to is not None and self.valid_from > self.valid_to:
            raise DomainValidationError(
                "適用終了日は適用開始日以降で指定してください。"
            )

    def overlaps(self, other: CoveragePeriod) -> bool:
        """この期間と別の期間が1日でも重なるかを返す。"""
        left_ends_before_right_starts = (
            self.valid_to is not None and self.valid_to < other.valid_from
        )
        right_ends_before_left_starts = (
            other.valid_to is not None and other.valid_to < self.valid_from
        )
        return not (left_ends_before_right_starts or right_ends_before_left_starts)


@dataclass(frozen=True, kw_only=True)
class InsuranceCoverageDetails:
    """健康保険資格の制度別詳細。"""

    insurer_number: CoverageCode
    insured_symbol: CoverageSymbol
    insured_number: CoverageCode
    insured_type: CoverageInsuredType
    benefit_ratio: CoverageBenefitRatio
    branch_number: CoverageBranchNumber | None = None


@dataclass(frozen=True, kw_only=True)
class PublicExpenseCoverageDetails:
    """公費負担資格の制度別詳細。"""

    payer_number: PublicPayerNumber
    recipient_number: PublicRecipientNumber
