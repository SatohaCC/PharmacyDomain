"""調剤日（受付日）において処方に適用する健康保険証および公費負担医療（第一〜第四公費）の組み合わせを管理するモジュール。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import ClassVar

from app.domain.corporate.identifiers import CorporateId
from app.domain.coverage.exceptions import CoverageCombinationError
from app.domain.coverage.identifiers import PatientCoverageId
from app.domain.coverage.primitives import CoveragePriority, CoverageType
from app.domain.coverage.priority_rules import (
    PriorityViolation,
    find_priority_violation,
)
from app.domain.coverage.value_objects import (
    InsuranceCoverageDetails,
    PublicExpenseCoverageDetails,
)
from app.domain.foundation.value_object import ValueObject
from app.domain.patient.identifiers import PatientId

#: 公費は第一公費から第四公費までを同時に適用できる。
MAXIMUM_PUBLIC_EXPENSE_COUNT = 4

#: 順位規則の違反種別に対応する日本語メッセージ。規則本体は Shared Kernel の
#: :func:`find_priority_violation` に1つだけ置き、文言だけを各コンテキストが持つ。
PUBLIC_EXPENSE_PRIORITY_MESSAGES: Mapping[PriorityViolation, str] = {
    PriorityViolation.EXCEEDS_MAXIMUM: "公費は第四公費まで指定できます。",
    PriorityViolation.DUPLICATED: "公費の適用順位は重複して指定できません。",
    PriorityViolation.NOT_CONSECUTIVE: (
        "公費の適用順位は第一公費から連続して指定してください。"
    ),
}


@dataclass(frozen=True, kw_only=True)
class SelectedInsuranceCoverage(ValueObject):
    """処方受付時に選択・適用された健康保険資格（主保険）の控えデータ。"""

    source_coverage_id: PatientCoverageId
    corporate_id: CorporateId
    patient_id: PatientId
    applied_on: date
    coverage_type: CoverageType
    priority: CoveragePriority
    details: InsuranceCoverageDetails

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "source_coverage_id": "選択元患者資格ID",
        "corporate_id": "法人ID",
        "patient_id": "患者ID",
        "applied_on": "適用日",
        "coverage_type": "資格種別",
        "priority": "適用順位",
        "details": "医療保険詳細",
    }

    def validate(self) -> None:
        """医療保険枠の種別と順位を検証する。"""
        if self.coverage_type is not CoverageType.INSURANCE:
            raise CoverageCombinationError("医療保険枠には医療保険資格が必要です。")
        if self.priority.value != 1:
            raise CoverageCombinationError(
                "医療保険の適用順位は1である必要があります。"
            )


@dataclass(frozen=True, kw_only=True)
class SelectedPublicExpenseCoverage(ValueObject):
    """処方受付時に選択・適用された公費負担医療（第一〜第四公費）の控えデータ。"""

    source_coverage_id: PatientCoverageId
    corporate_id: CorporateId
    patient_id: PatientId
    applied_on: date
    coverage_type: CoverageType
    priority: CoveragePriority
    details: PublicExpenseCoverageDetails

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "source_coverage_id": "選択元患者資格ID",
        "corporate_id": "法人ID",
        "patient_id": "患者ID",
        "applied_on": "適用日",
        "coverage_type": "資格種別",
        "priority": "適用順位",
        "details": "公費詳細",
    }

    def validate(self) -> None:
        """公費枠へ公費資格だけが入ることを検証する。"""
        if self.coverage_type is not CoverageType.PUBLIC_EXPENSE:
            raise CoverageCombinationError("公費枠には公費資格が必要です。")


@dataclass(frozen=True, kw_only=True)
class CoverageCombination(ValueObject):
    """処方受付時に確定した健康保険（主保険 0〜1件）と公費負担医療（第一〜第四公費）の組み合わせ。"""

    insurance: SelectedInsuranceCoverage | None = None
    public_expenses: tuple[SelectedPublicExpenseCoverage, ...] = ()

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "insurance": "医療保険資格",
        "public_expenses": "公費資格",
    }

    def _normalize_fields(self) -> None:
        """公費を適用順位順へ正規化する。"""
        if not isinstance(self.public_expenses, tuple) or not all(
            isinstance(item, SelectedPublicExpenseCoverage)
            for item in self.public_expenses
        ):
            return
        ordered = tuple(
            sorted(self.public_expenses, key=lambda item: item.priority.value)
        )
        object.__setattr__(self, "public_expenses", ordered)

    def validate(self) -> None:
        """件数・順位・テナント・患者・適用日の一貫性を検証する。"""
        selected = self._all_selected()
        if not selected:
            raise CoverageCombinationError("適用資格を1件以上指定してください。")

        violation = find_priority_violation(
            [item.priority.value for item in self.public_expenses],
            maximum=MAXIMUM_PUBLIC_EXPENSE_COUNT,
        )
        if violation is not None:
            raise CoverageCombinationError(PUBLIC_EXPENSE_PRIORITY_MESSAGES[violation])

        first = selected[0]
        if any(item.corporate_id != first.corporate_id for item in selected[1:]):
            raise CoverageCombinationError("異なる法人の資格は組み合わせられません。")
        if any(item.patient_id != first.patient_id for item in selected[1:]):
            raise CoverageCombinationError("異なる患者の資格は組み合わせられません。")
        if any(item.applied_on != first.applied_on for item in selected[1:]):
            raise CoverageCombinationError("異なる適用日の資格は組み合わせられません。")

    def _all_selected(
        self,
    ) -> tuple[SelectedInsuranceCoverage | SelectedPublicExpenseCoverage, ...]:
        """医療保険を先頭、公費を順位順にした選択列を返す。"""
        insurance = (self.insurance,) if self.insurance is not None else ()
        return insurance + self.public_expenses
