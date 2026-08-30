"""資格台帳コンテキストのユースケース束。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.composition.coverage_references import (
    CoveragePatientReferenceAdapter,
)
from app.application.corporate.corporate_access import CorporateAccessService
from app.application.coverage.change_patient_coverage_period import (
    ChangePatientCoveragePeriodUseCase,
)
from app.application.coverage.deactivate_patient_coverage import (
    DeactivatePatientCoverageUseCase,
)
from app.application.coverage.get_patient_coverage import GetPatientCoverageUseCase
from app.application.coverage.list_patient_coverages import ListPatientCoveragesUseCase
from app.application.coverage.register_patient_coverage import (
    RegisterPatientCoverageUseCase,
)
from app.domain.coverage.services import PatientCoverageConflictService
from app.infrastructure.composition.repositories import PostgresRepositorySet


@dataclass(frozen=True, slots=True)
class CoverageUseCases:
    """資格台帳コンテキストのユースケース。"""

    register: RegisterPatientCoverageUseCase
    get: GetPatientCoverageUseCase
    list_by_patient: ListPatientCoveragesUseCase
    change_period: ChangePatientCoveragePeriodUseCase
    deactivate: DeactivatePatientCoverageUseCase


def build_coverage_use_cases(
    repositories: PostgresRepositorySet,
    corporate_access: CorporateAccessService,
) -> CoverageUseCases:
    """資格台帳ユースケースを組み立てる。"""
    repository = repositories.patient_coverage
    patient_reference = CoveragePatientReferenceAdapter(repositories.patient)
    conflict = PatientCoverageConflictService()
    return CoverageUseCases(
        register=RegisterPatientCoverageUseCase(
            repository, patient_reference, conflict, corporate_access
        ),
        get=GetPatientCoverageUseCase(repository, corporate_access),
        list_by_patient=ListPatientCoveragesUseCase(
            repository, patient_reference, corporate_access
        ),
        change_period=ChangePatientCoveragePeriodUseCase(
            repository, conflict, corporate_access
        ),
        deactivate=DeactivatePatientCoverageUseCase(repository, corporate_access),
    )
