"""患者・資格台帳・受付のユースケース束。

受付までに患者を特定して資格を選ぶ流れの3コンテキストをまとめる。
資格の構築と再検証は ``app/application/composition`` の実アダプタが担う。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.common.clock import Clock
from app.application.composition.coverage_references import (
    CoveragePatientReferenceAdapter,
)
from app.application.composition.coverage_selection_adapter import (
    CoverageSelectionAdapter,
)
from app.application.composition.reception_references import (
    ReceptionPatientReferenceAdapter,
    ReceptionStoreReferenceAdapter,
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
from app.application.patient.change_patient_birth_date import (
    ChangePatientBirthDateUseCase,
)
from app.application.patient.change_patient_names import ChangePatientNamesUseCase
from app.application.patient.deactivate_patient_external_identifier import (
    DeactivatePatientExternalIdentifierUseCase,
)
from app.application.patient.get_patient import GetPatientUseCase
from app.application.patient.get_patient_external_identifier import (
    GetPatientExternalIdentifierUseCase,
)
from app.application.patient.list_patient_external_identifiers import (
    ListPatientExternalIdentifiersUseCase,
)
from app.application.patient.register_patient import RegisterPatientUseCase
from app.application.patient.register_patient_external_identifier import (
    RegisterPatientExternalIdentifierUseCase,
)
from app.application.reception.get_last_coverage_selection import (
    GetLastCoverageSelectionUseCase,
)
from app.application.reception.record_coverage_selection import (
    RecordCoverageSelectionUseCase,
)
from app.domain.coverage.combination import CoverageSelectionService
from app.domain.coverage.services import PatientCoverageConflictService
from app.infrastructure.postgres.repositories import PostgresRepositorySet

# --------------------------------------------------------------------------
# 患者
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PatientUseCases:
    """患者コンテキストのユースケース。"""

    register: RegisterPatientUseCase
    get: GetPatientUseCase
    change_names: ChangePatientNamesUseCase
    change_birth_date: ChangePatientBirthDateUseCase
    register_external_identifier: RegisterPatientExternalIdentifierUseCase
    get_external_identifier: GetPatientExternalIdentifierUseCase
    list_external_identifiers: ListPatientExternalIdentifiersUseCase
    deactivate_external_identifier: DeactivatePatientExternalIdentifierUseCase


def build_patient_use_cases(
    repositories: PostgresRepositorySet,
    corporate_access: CorporateAccessService,
) -> PatientUseCases:
    """患者ユースケースを組み立てる。"""
    patient_repository = repositories.patient
    identifier_repository = repositories.patient_external_identifier
    return PatientUseCases(
        register=RegisterPatientUseCase(patient_repository, corporate_access),
        get=GetPatientUseCase(patient_repository, corporate_access),
        change_names=ChangePatientNamesUseCase(patient_repository, corporate_access),
        change_birth_date=ChangePatientBirthDateUseCase(
            patient_repository, corporate_access
        ),
        register_external_identifier=RegisterPatientExternalIdentifierUseCase(
            patient_repository, identifier_repository, corporate_access
        ),
        get_external_identifier=GetPatientExternalIdentifierUseCase(
            identifier_repository, corporate_access
        ),
        list_external_identifiers=ListPatientExternalIdentifiersUseCase(
            patient_repository, identifier_repository, corporate_access
        ),
        deactivate_external_identifier=DeactivatePatientExternalIdentifierUseCase(
            identifier_repository, corporate_access
        ),
    )


# --------------------------------------------------------------------------
# 資格台帳
# --------------------------------------------------------------------------


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


# --------------------------------------------------------------------------
# 受付
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ReceptionUseCases:
    """受付コンテキストのユースケース。"""

    record_coverage_selection: RecordCoverageSelectionUseCase
    get_last_coverage_selection: GetLastCoverageSelectionUseCase


def build_reception_use_cases(
    repositories: PostgresRepositorySet,
    corporate_access: CorporateAccessService,
    clock: Clock,
) -> ReceptionUseCases:
    """受付ユースケースを組み立てる。

    資格の構築（登録時）と再検証（参照時）は同一のアダプタが担う。**同じ規則で
    組み立て直せること**が履歴の真正性の定義なので、別実装に分けると、記録した
    ときの規則と検証するときの規則が食い違いうる。
    """
    repository = repositories.coverage_selection_record
    store_reference = ReceptionStoreReferenceAdapter(repositories.store)
    patient_reference = ReceptionPatientReferenceAdapter(repositories.patient)
    coverage_selection = CoverageSelectionAdapter(
        repositories.patient_coverage, CoverageSelectionService()
    )
    return ReceptionUseCases(
        record_coverage_selection=RecordCoverageSelectionUseCase(
            repository,
            corporate_access,
            store_reference,
            patient_reference,
            coverage_selection,
            clock,
        ),
        get_last_coverage_selection=GetLastCoverageSelectionUseCase(
            repository,
            corporate_access,
            store_reference,
            patient_reference,
            coverage_selection,
        ),
    )
