"""患者資格取得ユースケース。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control import CorporateAccessBoundary, Permission
from app.application.coverage.support import load_coverage_or_raise
from app.domain.corporate.primitives import CorporateId
from app.domain.coverage import PatientCoverage, PatientCoverageId
from app.domain.coverage.repository import PatientCoverageRepository


@dataclass(frozen=True, kw_only=True)
class PatientCoverageDto:
    """患者資格の出力データ（DTO）。"""

    id: str
    corporate_id: str
    patient_id: str
    coverage_type: str
    valid_from: str
    valid_to: str | None
    priority: int
    is_active: bool
    insurer_number: str | None
    insured_symbol: str | None
    insured_number: str | None
    branch_number: str | None
    insured_type: str | None
    benefit_ratio: int | None
    payer_number: str | None
    recipient_number: str | None

    @classmethod
    def from_entity(cls, coverage: PatientCoverage) -> PatientCoverageDto:
        """患者資格集約からDTOを生成する。"""
        insurance = coverage.insurance_details
        public_expense = coverage.public_expense_details
        return cls(
            id=str(coverage.id.value),
            corporate_id=str(coverage.corporate_id.value),
            patient_id=str(coverage.patient_id.value),
            coverage_type=coverage.coverage_type.value,
            valid_from=coverage.period.valid_from.value.isoformat(),
            valid_to=(
                coverage.period.valid_to.value.isoformat()
                if coverage.period.valid_to is not None
                else None
            ),
            priority=coverage.priority.value,
            is_active=coverage.is_active,
            insurer_number=(insurance.insurer_number.value if insurance else None),
            insured_symbol=(insurance.insured_symbol.value if insurance else None),
            insured_number=(insurance.insured_number.value if insurance else None),
            branch_number=(
                insurance.branch_number.value
                if insurance and insurance.branch_number
                else None
            ),
            insured_type=(insurance.insured_type.value if insurance else None),
            benefit_ratio=(insurance.benefit_ratio.value if insurance else None),
            payer_number=(
                public_expense.payer_number.value if public_expense else None
            ),
            recipient_number=(
                public_expense.recipient_number.value if public_expense else None
            ),
        )


@dataclass(frozen=True, kw_only=True)
class GetPatientCoverageQuery:
    """患者資格取得の入力データ（DTO）。"""

    corporate_id: str
    coverage_id: str


class GetPatientCoverageUseCase:
    """患者資格を取得してDTOを返すアプリケーションサービス。"""

    def __init__(
        self,
        repository: PatientCoverageRepository,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access

    async def execute(self, query: GetPatientCoverageQuery) -> PatientCoverageDto:
        """法人境界を確認して患者資格DTOを返す。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.VIEW_COVERAGE,
        )
        coverage_id = PatientCoverageId.parse(query.coverage_id)
        coverage = await load_coverage_or_raise(
            self._repository,
            corporate_id=corporate_id,
            coverage_id=coverage_id,
        )
        return PatientCoverageDto.from_entity(coverage)
