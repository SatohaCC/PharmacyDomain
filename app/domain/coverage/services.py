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
        """同一制度・同一順位の有効期間が重複していないことを検証する。

        医療保険は :class:`PatientCoverage` が適用順位を1に固定するため、
        「同一制度かつ同一順位」の判定がそのまま「同一患者・同一期間に医療保険は
        1件」の規則になる。公費は第一から第四までを別枠として扱うので、順位が
        違えば同一期間でも併用できる。保険の枠を ``coverage_type`` で別途判定
        しても順位固定により結果は変わらないため、条件は1つに保つ。
        """
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
