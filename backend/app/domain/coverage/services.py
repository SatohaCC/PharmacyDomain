"""coverageのドメインサービス。"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime

from app.domain.corporate.identifiers import CorporateId
from app.domain.coverage.entities import PatientCoverage
from app.domain.coverage.exceptions import (
    CoverageCombinationError,
    CoveragePeriodConflictError,
)
from app.domain.coverage.identifiers import PatientCoverageId
from app.domain.coverage.primitives import CoverageType
from app.domain.coverage.value_objects import (
    CoverageCombination,
    SelectedInsuranceCoverage,
    SelectedPublicExpenseCoverage,
)
from app.domain.patient.identifiers import PatientId


class PatientCoverageConflictService:
    """同一患者において健康保険証や公費の有効期間が重複していないかを検証する。"""

    def ensure_no_conflict(
        self,
        coverage: PatientCoverage,
        existing_coverages: Iterable[PatientCoverage],
    ) -> None:
        """同一制度・同一適用順位の有効期間が重複していないことを検証する。

        健康保険（主保険）は適用順位が1に固定されるため、同一患者・同一期間に
        複数の主保険が有効になる二重登録を防止します。
        公費（第一〜第四公費）は順位が異なれば同一期間でも併用可能です。
        """
        effective_period = coverage.effective_period()
        if effective_period is None:
            return
        for existing in existing_coverages:
            if existing.id == coverage.id:
                continue
            existing_effective_period = existing.effective_period()
            if existing_effective_period is None:
                continue
            if (
                existing.corporate_id == coverage.corporate_id
                and existing.patient_id == coverage.patient_id
                and existing.coverage_type is coverage.coverage_type
                and existing.priority == coverage.priority
                and existing_effective_period.overlaps(effective_period)
            ):
                raise CoveragePeriodConflictError()


class CoverageSelectionService:
    """患者の有効な保険資格台帳から、受付日時点で有効な保険・公費の組み合わせ（併用関係）を検証・構築するドメインサービス。"""

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
            public_expenses=tuple(
                sorted(public_expenses, key=lambda item: item.priority.value)
            ),
        )
