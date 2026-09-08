"""患者資格の PostgreSQL Repository。

「同一患者・同一順位で実効期間が重なる資格を拒否する」は一意制約では表せない
ので、``daterange`` と排他制約が最終防衛になる。Applicationの事前readは早期
エラー用であって、原子性の代替ではない。
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import Range

from app.domain.corporate.primitives import CorporateId
from app.domain.coverage.exceptions import CoveragePeriodConflictError
from app.domain.coverage.patient_coverage import PatientCoverage
from app.domain.coverage.primitives import PatientCoverageId
from app.domain.coverage.repository import PatientCoverageRepository
from app.domain.patient.primitives import PatientId
from app.infrastructure.postgres.repository_base import (
    AggregateMapping,
    PostgresRepositoryBase,
)
from app.infrastructure.postgres.schema import patient_coverages


def effective_range(coverage: PatientCoverage) -> Range[date] | None:
    """実効期間を PostgreSQL の日付範囲へ変換する。

    ``CoveragePeriod`` は終了日を**含む**閉区間なので境界は ``[]`` にする。
    終了日が無ければ上端なしの範囲になる。実効期間が空（無効化発効日が
    開始日以前など）のときは ``None`` を返し、競合判定の対象から外す。
    """
    period = coverage.effective_period()
    if period is None:
        return None
    upper = None if period.valid_to is None else period.valid_to.value
    return Range(period.valid_from.value, upper, bounds="[]")


def _coverage_columns(coverage: PatientCoverage) -> dict[str, object]:
    """検索・競合判定に使う列を資格から導く。"""
    return {
        "id": coverage.id.value,
        "corporate_id": coverage.corporate_id.value,
        "patient_id": coverage.patient_id.value,
        "coverage_type": coverage.coverage_type.value,
        "priority": coverage.priority.value,
        "effective_range": effective_range(coverage),
    }


PATIENT_COVERAGE_MAPPING = AggregateMapping(
    table=patient_coverages,
    aggregate_type=PatientCoverage,
    label="患者資格",
    search_columns=_coverage_columns,
)


class PostgresPatientCoverageRepository(
    PostgresRepositoryBase, PatientCoverageRepository
):
    """患者資格集約を PostgreSQL へ保存・検索する。"""

    async def get(
        self,
        *,
        corporate_id: CorporateId,
        coverage_id: PatientCoverageId,
    ) -> PatientCoverage | None:
        """法人境界を含めてIDで資格を検索する。"""
        return await self.get_by_id(
            PATIENT_COVERAGE_MAPPING, coverage_id, corporate_id=corporate_id
        )

    async def list_by_patient(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
    ) -> list[PatientCoverage]:
        """法人・患者の資格を制度・順位・ID順で返す。"""
        return await self.find_all(
            PATIENT_COVERAGE_MAPPING,
            select(patient_coverages)
            .where(
                patient_coverages.c.corporate_id == corporate_id.value,
                patient_coverages.c.patient_id == patient_id.value,
            )
            .order_by(
                patient_coverages.c.coverage_type,
                patient_coverages.c.priority,
                patient_coverages.c.id,
            ),
        )

    async def save(self, coverage: PatientCoverage) -> None:
        """実効期間の競合を原子的に拒否して資格を保存する。

        「期間が重なる」は一意制約では表せないため、排他制約が最終防衛になる。
        """
        await self.save_with_conflict_map(
            PATIENT_COVERAGE_MAPPING,
            coverage,
            conflicts={
                "excl_patient_coverages_effective_period": CoveragePeriodConflictError
            },
        )
