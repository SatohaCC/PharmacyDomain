"""患者資格登録ユースケース。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.application.access_control import CorporateAccessBoundary, Permission
from app.application.coverage.get_patient_coverage import PatientCoverageDto
from app.application.coverage.reference import PatientReferenceBoundary
from app.application.coverage.support import (
    build_activation,
    build_coverage_period,
    build_insurance_details,
    build_priority,
    build_public_expense_details,
    parse_coverage_type,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.coverage import (
    CoverageType,
    PatientCoverage,
    PatientCoverageConflictService,
)
from app.domain.coverage.repository import PatientCoverageRepository
from app.domain.patient.primitives import PatientId


@dataclass(frozen=True, kw_only=True)
class RegisterPatientCoverageCommand:
    """患者資格登録の入力データ（DTO）。"""

    corporate_id: str
    patient_id: str
    coverage_type: str
    valid_from: date
    activated_on: date
    valid_to: date | None = None
    priority: int = 1
    insurer_number: str | None = None
    insured_symbol: str | None = None
    insured_number: str | None = None
    branch_number: str | None = None
    insured_type: str | None = None
    benefit_ratio: int | None = None
    payer_number: str | None = None
    recipient_number: str | None = None


class RegisterPatientCoverageUseCase:
    """患者資格を登録するアプリケーションサービス。"""

    def __init__(
        self,
        repository: PatientCoverageRepository,
        patient_reference: PatientReferenceBoundary,
        conflict_service: PatientCoverageConflictService,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._repository = repository
        self._patient_reference = patient_reference
        self._conflict_service = conflict_service
        self._corporate_access = corporate_access

    async def execute(
        self,
        command: RegisterPatientCoverageCommand,
    ) -> PatientCoverageDto:
        """法人・患者の存在を確認して患者資格を登録する。"""
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.MANAGE_COVERAGE,
        )
        patient_id = PatientId.parse(command.patient_id)
        await self._patient_reference.require_exists(
            corporate_id=corporate_id,
            patient_id=patient_id,
        )
        coverage_type = parse_coverage_type(command.coverage_type)
        period = build_coverage_period(
            valid_from=command.valid_from,
            valid_to=command.valid_to,
        )
        insurance_details = None
        public_expense_details = None
        if coverage_type is CoverageType.INSURANCE:
            insurance_details = build_insurance_details(
                insurer_number=command.insurer_number,
                insured_symbol=command.insured_symbol,
                insured_number=command.insured_number,
                branch_number=command.branch_number,
                insured_type=command.insured_type,
                benefit_ratio=command.benefit_ratio,
            )
        else:
            public_expense_details = build_public_expense_details(
                payer_number=command.payer_number,
                recipient_number=command.recipient_number,
            )
        coverage = PatientCoverage.create(
            corporate_id=corporate_id,
            patient_id=patient_id,
            coverage_type=coverage_type,
            period=period,
            activation=build_activation(activated_on=command.activated_on),
            priority=build_priority(command.priority),
            insurance_details=insurance_details,
            public_expense_details=public_expense_details,
        )
        existing = await self._repository.list_by_patient(
            corporate_id=corporate_id,
            patient_id=patient_id,
        )
        self._conflict_service.ensure_no_conflict(coverage, existing)
        await self._repository.save(coverage)
        return PatientCoverageDto.from_entity(coverage)
