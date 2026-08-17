"""患者資格期間変更ユースケース。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.application.access_control import CorporateAccessBoundary, Permission
from app.application.coverage.get_patient_coverage import PatientCoverageDto
from app.application.coverage.support import (
    build_coverage_period,
    load_coverage_or_raise,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.coverage import PatientCoverageConflictService, PatientCoverageId
from app.domain.coverage.repository import PatientCoverageRepository


@dataclass(frozen=True, kw_only=True)
class ChangePatientCoveragePeriodCommand:
    """患者資格期間変更の入力データ（DTO）。"""

    corporate_id: str
    coverage_id: str
    valid_from: date
    valid_to: date | None = None


class ChangePatientCoveragePeriodUseCase:
    """患者資格の適用期間を変更する。"""

    def __init__(
        self,
        repository: PatientCoverageRepository,
        conflict_service: PatientCoverageConflictService,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._repository = repository
        self._conflict_service = conflict_service
        self._corporate_access = corporate_access

    async def execute(
        self,
        command: ChangePatientCoveragePeriodCommand,
    ) -> PatientCoverageDto:
        """法人境界を確認して患者資格期間を変更する。"""
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.MANAGE_COVERAGE,
        )
        coverage_id = PatientCoverageId.parse(command.coverage_id)
        coverage = await load_coverage_or_raise(
            self._repository,
            corporate_id=corporate_id,
            coverage_id=coverage_id,
        )
        changed = coverage.change_period(
            build_coverage_period(
                valid_from=command.valid_from,
                valid_to=command.valid_to,
            )
        )
        existing = await self._repository.list_by_patient(
            corporate_id=corporate_id,
            patient_id=coverage.patient_id,
        )
        self._conflict_service.ensure_no_conflict(changed, existing)
        await self._repository.save(changed)
        return PatientCoverageDto.from_entity(changed)
