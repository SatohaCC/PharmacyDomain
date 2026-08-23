"""適用日に選択した患者資格の不変な組み合わせ。"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import ClassVar

from app.base.domain.priority_rules import (
    PriorityViolation,
    find_priority_violation,
)
from app.base.domain.value_object import ValueObject
from app.domain.corporate.primitives import CorporateId
from app.domain.coverage.exceptions import CoverageCombinationError
from app.domain.coverage.patient_coverage import PatientCoverage
from app.domain.coverage.primitives import (
    CoveragePriority,
    CoverageType,
    InsuranceCoverageDetails,
    PatientCoverageId,
    PublicExpenseCoverageDetails,
)
from app.domain.patient.primitives import PatientId

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
    """選択した医療保険資格のIDと不変な値投影。"""

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
    """選択した公費資格のIDと不変な値投影。"""

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
    """医療保険0〜1件と第一〜第四公費の選択投影。"""

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

    @property
    def source_coverage_ids(self) -> tuple[PatientCoverageId, ...]:
        """選択元IDを医療保険、公費順位順で返す。"""
        return tuple(item.source_coverage_id for item in self._all_selected())


class CoverageSelectionService:
    """明示された患者資格だけから適用組み合わせを構築する。"""

    def build_selection(
        self,
        *,
        coverages: Iterable[PatientCoverage],
        requested_ids: tuple[PatientCoverageId, ...],
        corporate_id: CorporateId,
        patient_id: PatientId,
        applied_on: date,
    ) -> CoverageCombination:
        """ID集合・境界・適用日の実効性を検証して値投影を返す。"""
        if not isinstance(applied_on, date) or isinstance(applied_on, datetime):
            raise CoverageCombinationError("適用日は日付型で指定してください。")
        if not requested_ids:
            raise CoverageCombinationError("適用資格IDを1件以上指定してください。")
        if not all(isinstance(item, PatientCoverageId) for item in requested_ids):
            raise CoverageCombinationError(
                "適用資格IDは PatientCoverageId で指定してください。"
            )
        if len(requested_ids) != len(set(requested_ids)):
            raise CoverageCombinationError("適用資格IDは重複して指定できません。")

        loaded = tuple(coverages)
        if not all(isinstance(item, PatientCoverage) for item in loaded):
            raise CoverageCombinationError(
                "患者資格は PatientCoverage で指定してください。"
            )
        loaded_ids = tuple(item.id for item in loaded)
        if len(loaded_ids) != len(set(loaded_ids)):
            raise CoverageCombinationError("同じ患者資格が重複して読み込まれました。")
        if set(loaded_ids) != set(requested_ids):
            raise CoverageCombinationError(
                "指定した患者資格を過不足なく取得できませんでした。"
            )

        insurance: list[SelectedInsuranceCoverage] = []
        public_expenses: list[SelectedPublicExpenseCoverage] = []
        for coverage in loaded:
            if (
                coverage.corporate_id != corporate_id
                or coverage.patient_id != patient_id
            ):
                raise CoverageCombinationError(
                    "指定法人・患者に属さない患者資格が含まれています。"
                )
            if not coverage.is_active_on(applied_on):
                raise CoverageCombinationError(
                    "適用日時点で有効でない患者資格が含まれています。"
                )

            if coverage.coverage_type is CoverageType.INSURANCE:
                if coverage.insurance_details is None:
                    raise CoverageCombinationError("医療保険詳細がありません。")
                insurance.append(
                    SelectedInsuranceCoverage(
                        source_coverage_id=coverage.id,
                        corporate_id=coverage.corporate_id,
                        patient_id=coverage.patient_id,
                        applied_on=applied_on,
                        coverage_type=coverage.coverage_type,
                        priority=coverage.priority,
                        details=coverage.insurance_details,
                    )
                )
            else:
                if coverage.public_expense_details is None:
                    raise CoverageCombinationError("公費詳細がありません。")
                public_expenses.append(
                    SelectedPublicExpenseCoverage(
                        source_coverage_id=coverage.id,
                        corporate_id=coverage.corporate_id,
                        patient_id=coverage.patient_id,
                        applied_on=applied_on,
                        coverage_type=coverage.coverage_type,
                        priority=coverage.priority,
                        details=coverage.public_expense_details,
                    )
                )

        if len(insurance) > 1:
            raise CoverageCombinationError("医療保険は1件だけ選択できます。")
        return CoverageCombination(
            insurance=insurance[0] if insurance else None,
            public_expenses=tuple(public_expenses),
        )
