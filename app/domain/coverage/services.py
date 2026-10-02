"""保険証・公費受給者証（保険資格）の有効期間整合性に関わるドメインサービス。"""

from collections.abc import Iterable

from app.domain.coverage.exceptions import CoveragePeriodConflictError
from app.domain.coverage.patient_coverage import PatientCoverage


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
