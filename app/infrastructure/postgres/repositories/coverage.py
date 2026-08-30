"""患者資格の PostgreSQL Repository。"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import cast

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.exc import IntegrityError

from app.domain.corporate.primitives import CorporateId
from app.domain.coverage.exceptions import CoveragePeriodConflictError
from app.domain.coverage.patient_coverage import PatientCoverage
from app.domain.coverage.primitives import PatientCoverageId
from app.domain.coverage.repository import PatientCoverageRepository
from app.domain.patient.primitives import PatientId
from app.infrastructure.postgres.codec import (
    PersistenceMappingError,
    decode_aggregate,
    encode_aggregate,
)
from app.infrastructure.postgres.constraints import constraint_name
from app.infrastructure.postgres.repository_base import (
    PostgresRepositoryBase,
    closed_date_range_matches,
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


def row_values(coverage: PatientCoverage) -> dict[str, object]:
    """集約から、payload と検索・競合判定用の列を組み立てる。"""
    return {
        "id": coverage.id.value,
        "corporate_id": coverage.corporate_id.value,
        "patient_id": coverage.patient_id.value,
        "coverage_type": coverage.coverage_type.value,
        "priority": coverage.priority.value,
        "effective_range": effective_range(coverage),
        "payload": encode_aggregate(coverage),
    }


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
        result = await self.session.execute(
            select(patient_coverages).where(
                patient_coverages.c.corporate_id == corporate_id.value,
                patient_coverages.c.id == coverage_id.value,
            )
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None
        return _decode_row(
            self.remember_version(
                cast(Mapping[str, object], row),
                namespace=patient_coverages.name,
            )
        )

    async def list_by_patient(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
    ) -> list[PatientCoverage]:
        """法人・患者の資格を制度・順位・ID順で返す。"""
        result = await self.session.execute(
            select(patient_coverages)
            .where(
                patient_coverages.c.corporate_id == corporate_id.value,
                patient_coverages.c.patient_id == patient_id.value,
            )
            .order_by(
                patient_coverages.c.coverage_type,
                patient_coverages.c.priority,
                patient_coverages.c.id,
            )
        )
        return [
            _decode_row(
                self.remember_version(
                    cast(Mapping[str, object], row),
                    namespace=patient_coverages.name,
                )
            )
            for row in result.mappings().all()
        ]

    async def save(self, coverage: PatientCoverage) -> None:
        """実効期間の競合を原子的に拒否して資格を保存する。

        「期間が重なる」は一意制約では表せないため、排他制約が最終防衛になる。
        """
        try:
            await self.upsert(
                patient_coverages,
                aggregate_id=coverage.id.value,
                values=row_values(coverage),
            )
        except IntegrityError as error:
            if constraint_name(error) == "excl_patient_coverages_effective_period":
                raise CoveragePeriodConflictError() from error
            raise


def _decode_row(row: Mapping[str, object]) -> PatientCoverage:
    """DB行の検索列と payload の整合性を確認して復元する。"""
    payload = row.get("payload")
    if not isinstance(payload, Mapping):
        raise PersistenceMappingError(
            "患者資格の payload が JSON オブジェクトではありません。"
        )
    coverage = decode_aggregate(payload, PatientCoverage)
    if (
        coverage.id.value != row.get("id")
        or coverage.corporate_id.value != row.get("corporate_id")
        or coverage.patient_id.value != row.get("patient_id")
        or coverage.coverage_type.value != row.get("coverage_type")
        or coverage.priority.value != row.get("priority")
        or not closed_date_range_matches(
            row.get("effective_range"),
            effective_range(coverage),
        )
    ):
        raise PersistenceMappingError("患者資格の検索列と payload が一致しません。")
    return coverage
