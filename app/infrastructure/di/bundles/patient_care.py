"""患者・資格台帳・受付のユースケース束。

受付までに患者を特定して資格を選ぶ流れの3コンテキストをまとめる。
資格の構築と再検証は ``app/application/composition`` の実アダプタが担う。"""

from __future__ import annotations

from app.application.common.clock import Clock
from app.application.composition.coverage_references import (
    CoveragePatientReferenceAdapter,
    CoverageStoreReferenceAdapter,
)
from app.application.composition.patient_references import (
    PatientStoreReferenceAdapter,
)
from app.application.composition.reception_medication_history import (
    ReceptionMedicationHistoryAssociationAdapter,
)
from app.application.composition.use_case_bundles import (
    CoverageUseCases,
    PatientUseCases,
    ReceptionUseCases,
)
from app.application.corporate.corporate_access import CorporateAccessService
from app.application.coverage.change_patient_coverage_period import (
    ChangePatientCoveragePeriodUseCase,
)
from app.application.coverage.deactivate_patient_coverage import (
    DeactivatePatientCoverageUseCase,
)
from app.application.coverage.get_last_coverage_selection import (
    GetLastCoverageSelectionUseCase,
)
from app.application.coverage.get_patient_coverage import GetPatientCoverageUseCase
from app.application.coverage.list_patient_coverages import ListPatientCoveragesUseCase
from app.application.coverage.record_coverage_selection import (
    RecordCoverageSelectionUseCase,
)
from app.application.coverage.register_patient_coverage import (
    RegisterPatientCoverageUseCase,
)
from app.application.coverage.selection import CoverageSelectionBuilder
from app.application.patient.change_patient_birth_date import (
    ChangePatientBirthDateUseCase,
)
from app.application.patient.change_patient_heading import (
    ChangePatientHeadingUseCase,
)
from app.application.patient.change_patient_names import ChangePatientNamesUseCase
from app.application.patient.change_patient_profile import ChangePatientProfileUseCase
from app.application.patient.deactivate_patient import DeactivatePatientUseCase
from app.application.patient.deactivate_patient_external_identifier import (
    DeactivatePatientExternalIdentifierUseCase,
)
from app.application.patient.get_patient import GetPatientUseCase
from app.application.patient.get_patient_external_identifier import (
    GetPatientExternalIdentifierUseCase,
)
from app.application.patient.get_patient_heading import GetPatientHeadingUseCase
from app.application.patient.list_patient_external_identifiers import (
    ListPatientExternalIdentifiersUseCase,
)
from app.application.patient.merge_patients import MergePatientsUseCase
from app.application.patient.reactivate_patient import ReactivatePatientUseCase
from app.application.patient.register_patient import RegisterPatientUseCase
from app.application.patient.register_patient_external_identifier import (
    RegisterPatientExternalIdentifierUseCase,
)
from app.application.reception.associate_reception_medication_history import (
    AssociateReceptionMedicationHistoryUseCase,
)
from app.domain.coverage.services import (
    CoverageSelectionService,
    PatientCoverageConflictService,
)
from app.infrastructure.di.repositories import (
    PostgresRepositorySet,
)
from app.infrastructure.postgres.connection import PostgresUnitOfWork

# --------------------------------------------------------------------------
# 患者
# --------------------------------------------------------------------------


def build_patient_use_cases(
    repositories: PostgresRepositorySet,
    corporate_access: CorporateAccessService,
    clock: Clock,
) -> PatientUseCases:
    """患者ユースケースを組み立てる。"""
    patient_repository = repositories.patient
    identifier_repository = repositories.patient_external_identifier
    return PatientUseCases(
        register=RegisterPatientUseCase(patient_repository, corporate_access),
        get=GetPatientUseCase(patient_repository, corporate_access),
        change_names=ChangePatientNamesUseCase(
            patient_repository,
            corporate_access,
            clock,
        ),
        change_birth_date=ChangePatientBirthDateUseCase(
            patient_repository,
            corporate_access,
            clock,
        ),
        deactivate=DeactivatePatientUseCase(
            patient_repository, corporate_access, clock
        ),
        reactivate=ReactivatePatientUseCase(
            patient_repository, corporate_access, clock
        ),
        merge=MergePatientsUseCase(patient_repository, corporate_access, clock),
        register_external_identifier=RegisterPatientExternalIdentifierUseCase(
            patient_repository,
            identifier_repository,
            corporate_access,
            store_reference=PatientStoreReferenceAdapter(repositories.store),
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
        change_profile=ChangePatientProfileUseCase(
            patient_repository,
            corporate_access,
            clock,
        ),
        get_heading=GetPatientHeadingUseCase(patient_repository, corporate_access),
        change_heading=ChangePatientHeadingUseCase(
            patient_repository, corporate_access, clock
        ),
    )


# --------------------------------------------------------------------------
# 資格台帳
# --------------------------------------------------------------------------


def build_coverage_use_cases(
    repositories: PostgresRepositorySet,
    corporate_access: CorporateAccessService,
    clock: Clock,
) -> CoverageUseCases:
    """資格台帳と適用選択ユースケースを組み立てる。"""
    repository = repositories.patient_coverage
    patient_reference = CoveragePatientReferenceAdapter(repositories.patient)
    store_reference = CoverageStoreReferenceAdapter(repositories.store)
    selection_repository = repositories.coverage_selection_record
    selection_builder = CoverageSelectionBuilder(
        repository,
        CoverageSelectionService(),
    )
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
        record_coverage_selection=RecordCoverageSelectionUseCase(
            selection_repository,
            corporate_access,
            store_reference,
            patient_reference,
            selection_builder,
            clock,
        ),
        get_last_coverage_selection=GetLastCoverageSelectionUseCase(
            selection_repository,
            corporate_access,
            store_reference,
            patient_reference,
            selection_builder,
        ),
    )


# --------------------------------------------------------------------------
# 受付
# --------------------------------------------------------------------------


def build_reception_use_cases(
    repositories: PostgresRepositorySet,
    corporate_access: CorporateAccessService,
    clock: Clock,
    unit_of_work: PostgresUnitOfWork,
) -> ReceptionUseCases:
    """受付固有の関連付けユースケースを組み立てる。"""
    return ReceptionUseCases(
        associate_medication_history=AssociateReceptionMedicationHistoryUseCase(
            reception_repository=repositories.reception,
            medication_history_reference=ReceptionMedicationHistoryAssociationAdapter(
                repositories.medication_history
            ),
            corporate_access=corporate_access,
            unit_of_work=unit_of_work,
        ),
    )


__all__ = [
    "CoverageUseCases",
    "PatientUseCases",
    "ReceptionUseCases",
    "build_coverage_use_cases",
    "build_patient_use_cases",
    "build_reception_use_cases",
]
