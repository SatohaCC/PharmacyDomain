"""患者資格集約。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Self

from app.base.domain.entity import AggregateRoot
from app.domain.corporate.primitives import CorporateId
from app.domain.coverage.exceptions import CoverageDetailsMismatchError
from app.domain.coverage.primitives import (
    CoveragePeriod,
    CoveragePriority,
    CoverageType,
    InsuranceCoverageDetails,
    PatientCoverageId,
    PublicExpenseCoverageDetails,
)
from app.domain.patient.primitives import PatientId


@dataclass(frozen=True, eq=False, kw_only=True)
class PatientCoverage(AggregateRoot[PatientCoverageId]):
    """保険または公費の患者資格を管理する集約ルート。"""

    id: PatientCoverageId
    corporate_id: CorporateId
    patient_id: PatientId
    coverage_type: CoverageType
    period: CoveragePeriod
    priority: CoveragePriority
    insurance_details: InsuranceCoverageDetails | None = None
    public_expense_details: PublicExpenseCoverageDetails | None = None
    is_active: bool = True

    def __post_init__(self) -> None:
        """制度種別と制度別詳細の整合性を検証する。"""
        if self.coverage_type is CoverageType.INSURANCE:
            if (
                self.insurance_details is None
                or self.public_expense_details is not None
            ):
                raise CoverageDetailsMismatchError()
        elif self.coverage_type is CoverageType.PUBLIC_EXPENSE and (
            self.public_expense_details is None or self.insurance_details is not None
        ):
            raise CoverageDetailsMismatchError()

    @classmethod
    def create(
        cls,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
        coverage_type: CoverageType,
        period: CoveragePeriod,
        priority: CoveragePriority,
        insurance_details: InsuranceCoverageDetails | None = None,
        public_expense_details: PublicExpenseCoverageDetails | None = None,
    ) -> Self:
        """新しい患者資格を生成する。"""
        return cls(
            id=PatientCoverageId.generate(),
            corporate_id=corporate_id,
            patient_id=patient_id,
            coverage_type=coverage_type,
            period=period,
            priority=priority,
            insurance_details=insurance_details,
            public_expense_details=public_expense_details,
        )

    def change_period(self, period: CoveragePeriod) -> Self:
        """患者資格の適用期間を変更する。"""
        return replace(self, period=period)

    def deactivate(self) -> Self:
        """患者資格を無効化する。"""
        return replace(self, is_active=False)
