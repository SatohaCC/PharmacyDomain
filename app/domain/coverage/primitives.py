"""Coverageコンテキストの識別子・資格情報プリミティブ。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from app.base.domain.exceptions import DomainValidationError
from app.base.domain.primitives.primitives import (
    BaseDate,
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


def _ensure_digits(value: str, *, field_name: str, lengths: tuple[int, ...]) -> None:
    """半角数字かつ規定桁数であることを検証する。

    保険者番号や公費負担者番号は、桁数が違えば電子レセプトの提出時に返戻される。
    登録時に弾かないと不正値がそのまま :class:`CoverageSnapshot` へ凍結され、
    請求まで気付けないため、桁数はプリミティブの不変条件として持たせる。
    """
    pattern = "|".join(f"[0-9]{{{length}}}" for length in lengths)
    if not re.fullmatch(pattern, value):
        expected = "桁または".join(str(length) for length in lengths)
        raise DomainValidationError(
            f"{field_name}は半角数字{expected}桁で指定してください。"
        )


class CoverageCode(BaseNormalizedString):
    """被保険者番号など、桁数が規定されていない保険・公費の符号。"""


class InsurerNumber(BaseNormalizedString):
    """保険者番号。国民健康保険は6桁、被用者保険は8桁の半角数字。"""

    def validate(self) -> None:
        super().validate()
        _ensure_digits(self.value, field_name="保険者番号", lengths=(6, 8))


class CoverageSymbol(BaseNormalizedString):
    """被保険者記号。桁数の規定はなく、空でないことだけを要求する。"""


class CoverageBranchNumber(BaseNormalizedString):
    """被保険者番号の枝番。半角数字2桁。"""

    def validate(self) -> None:
        super().validate()
        _ensure_digits(self.value, field_name="枝番", lengths=(2,))


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
        _ensure_digits(self.value, field_name="公費負担者番号", lengths=(8,))


class PublicRecipientNumber(BaseNormalizedString):
    """公費受給者番号。半角数字7桁。"""

    def validate(self) -> None:
        super().validate()
        _ensure_digits(self.value, field_name="公費受給者番号", lengths=(7,))


class CoverageValidFrom(BaseDate):
    """患者資格の適用開始日。"""


class CoverageValidTo(BaseDate):
    """患者資格の適用終了日。"""


@dataclass(frozen=True, kw_only=True)
class CoveragePeriod:
    """患者資格の適用期間。終了日なしは現在も有効であることを表す。

    日付型の検証は :class:`CoverageValidFrom` / :class:`CoverageValidTo` が
    :class:`BaseDate` から受け継ぐため、ここでは前後関係だけを検証する。
    """

    valid_from: CoverageValidFrom
    valid_to: CoverageValidTo | None = None

    def __post_init__(self) -> None:
        """適用開始日と適用終了日の前後関係を検証する。"""
        if self.valid_to is not None and self.valid_from.value > self.valid_to.value:
            raise DomainValidationError(
                "適用終了日は適用開始日以降で指定してください。"
            )

    def overlaps(self, other: CoveragePeriod) -> bool:
        """この期間と別の期間が1日でも重なるかを返す。"""
        left_ends_before_right_starts = (
            self.valid_to is not None and self.valid_to.value < other.valid_from.value
        )
        right_ends_before_left_starts = (
            other.valid_to is not None and other.valid_to.value < self.valid_from.value
        )
        return not (left_ends_before_right_starts or right_ends_before_left_starts)


@dataclass(frozen=True, kw_only=True)
class InsuranceCoverageDetails:
    """健康保険資格の制度別詳細。"""

    insurer_number: InsurerNumber
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
