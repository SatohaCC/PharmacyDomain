"""Coverage集約間のドメインサービス。"""

from collections.abc import Iterable

from app.domain.coverage.exceptions import CoveragePeriodConflictError
from app.domain.coverage.patient_coverage import PatientCoverage


class PatientCoverageConflictService:
    """同一患者における患者資格期間の競合を検証する。"""

    def ensure_no_conflict(
        self,
        coverage: PatientCoverage,
        existing_coverages: Iterable[PatientCoverage],
    ) -> None:
        """同一制度・優先順位の有効期間が重複していないことを検証する。"""
        if not coverage.is_active:
            return
        for existing in existing_coverages:
            if existing.id == coverage.id or not existing.is_active:
                continue
            if (
                existing.corporate_id == coverage.corporate_id
                and existing.patient_id == coverage.patient_id
                and existing.coverage_type is coverage.coverage_type
                and existing.priority == coverage.priority
                and existing.period.overlaps(coverage.period)
            ):
                raise CoveragePeriodConflictError()
