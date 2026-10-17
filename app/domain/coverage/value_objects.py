"""保険資格の有効期間・詳細・有効化事実を表す複合値。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import ClassVar

from app.domain.coverage.primitives import (
    CoverageActivatedOn,
    CoverageBenefitRatio,
    CoverageBranchNumber,
    CoverageCode,
    CoverageDeactivatedOn,
    CoverageInsuredType,
    CoverageSymbol,
    CoverageValidFrom,
    CoverageValidTo,
    InsurerNumber,
    PublicPayerNumber,
    PublicRecipientNumber,
)
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.foundation.value_object import ValueObject


@dataclass(frozen=True, kw_only=True)
class CoveragePeriod(ValueObject):
    """患者資格の適用期間。終了日なしは現在も有効であることを表す。

    日付型の検証は :class:`CoverageValidFrom` / :class:`CoverageValidTo` が
    :class:`BaseDate` から受け継ぐため、ここでは前後関係だけを検証する。
    """

    valid_from: CoverageValidFrom
    valid_to: CoverageValidTo | None = None

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "valid_from": "適用開始日",
        "valid_to": "適用終了日",
    }

    def validate(self) -> None:
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
class InsuranceCoverageDetails(ValueObject):
    """健康保険資格の制度別詳細。"""

    insurer_number: InsurerNumber
    insured_symbol: CoverageSymbol
    insured_number: CoverageCode
    insured_type: CoverageInsuredType | None
    benefit_ratio: CoverageBenefitRatio | None
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
class PublicExpenseCoverageDetails(ValueObject):
    """公費負担資格の制度別詳細。"""

    payer_number: PublicPayerNumber
    recipient_number: PublicRecipientNumber

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "payer_number": "公費負担者番号",
        "recipient_number": "公費受給者番号",
    }


@dataclass(frozen=True, kw_only=True)
class CoverageActivation(ValueObject):
    """患者資格台帳行の半開有効区間 ``[activated_on, deactivated_on)``。"""

    activated_on: CoverageActivatedOn
    deactivated_on: CoverageDeactivatedOn | None = None

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "activated_on": "有効化発効日",
        "deactivated_on": "無効化発効日",
    }

    def validate(self) -> None:
        """無効化発効日が有効化発効日より前でないことを検証する。"""
        if (
            self.deactivated_on is not None
            and self.deactivated_on.value < self.activated_on.value
        ):
            raise DomainValidationError(
                "無効化発効日は有効化発効日以降で指定してください。"
            )

    def is_active_on(self, target_date: date) -> bool:
        """指定日が半開有効区間に含まれるかを返す。"""
        if not isinstance(target_date, date) or isinstance(target_date, datetime):
            raise DomainValidationError("判定日は日付型で指定してください。")
        return self.activated_on.value <= target_date and (
            self.deactivated_on is None or target_date < self.deactivated_on.value
        )
