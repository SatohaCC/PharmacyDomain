"""患者資格無効化ユースケース。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control import CorporateAccessBoundary, Permission
from app.application.coverage.get_patient_coverage import PatientCoverageDto
from app.application.coverage.support import load_coverage_or_raise
from app.domain.corporate.primitives import CorporateId
from app.domain.coverage import PatientCoverageId
from app.domain.coverage.repository import PatientCoverageRepository


@dataclass(frozen=True, kw_only=True)
class DeactivatePatientCoverageCommand:
    """患者資格無効化の入力データ（DTO）。"""

    corporate_id: str
    coverage_id: str


class DeactivatePatientCoverageUseCase:
    """患者資格を無効化する。"""

    def __init__(
        self,
        repository: PatientCoverageRepository,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access

    async def execute(
        self,
        command: DeactivatePatientCoverageCommand,
    ) -> PatientCoverageDto:
        """法人境界を確認して患者資格を無効化する。"""
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
        changed = coverage.deactivate()
        await self._repository.save(changed)
        return PatientCoverageDto.from_entity(changed)
