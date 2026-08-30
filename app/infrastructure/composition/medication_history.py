"""薬歴コンテキストのユースケース束。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.common.clock import Clock
from app.application.composition.medication_history_references import (
    CounselorQualificationAdapter,
    DispensingSourceAdapter,
    MedicationHistoryStoreReferenceAdapter,
)
from app.application.corporate.corporate_access import CorporateAccessService
from app.application.medication_history.amend_medication_history import (
    AmendMedicationHistoryUseCase,
)
from app.application.medication_history.finalize_medication_history import (
    FinalizeMedicationHistoryUseCase,
)
from app.application.medication_history.get_medication_history import (
    GetMedicationHistoryUseCase,
    ListMedicationHistoriesByPatientUseCase,
)
from app.application.medication_history.get_patient_medical_profile import (
    GetPatientMedicalProfileUseCase,
    RebuildPatientMedicalProfileUseCase,
)
from app.application.medication_history.start_medication_history import (
    StartMedicationHistoryUseCase,
)
from app.application.medication_history.update_medication_history_draft import (
    UpdateMedicationHistoryDraftUseCase,
)
from app.domain.medication_history.services import CounselorQualificationService
from app.infrastructure.composition.repositories import PostgresRepositorySet
from app.infrastructure.postgres.unit_of_work import PostgresUnitOfWork


@dataclass(frozen=True, slots=True)
class MedicationHistoryUseCases:
    """薬歴コンテキストのユースケース。"""

    start: StartMedicationHistoryUseCase
    update_draft: UpdateMedicationHistoryDraftUseCase
    finalize: FinalizeMedicationHistoryUseCase
    amend: AmendMedicationHistoryUseCase
    get: GetMedicationHistoryUseCase
    list_by_patient: ListMedicationHistoriesByPatientUseCase
    get_medical_profile: GetPatientMedicalProfileUseCase
    rebuild_medical_profile: RebuildPatientMedicalProfileUseCase


def build_medication_history_use_cases(
    repositories: PostgresRepositorySet,
    corporate_access: CorporateAccessService,
    clock: Clock,
    unit_of_work: PostgresUnitOfWork,
) -> MedicationHistoryUseCases:
    """薬歴ユースケースを組み立てる。

    確定と再構築は薬歴と頭書きの2集約へ書く。どちらも同じスコープの
    トランザクションに入るので、頭書きだけが取り残されることはない。
    """
    record_repository = repositories.medication_history
    profile_repository = repositories.patient_medical_profile
    counselor_qualification = CounselorQualificationAdapter(repositories.staff)
    counselor = CounselorQualificationService()
    return MedicationHistoryUseCases(
        start=StartMedicationHistoryUseCase(
            record_repository,
            corporate_access,
            MedicationHistoryStoreReferenceAdapter(repositories.store),
            DispensingSourceAdapter(repositories.dispensing),
            counselor_qualification,
            counselor,
            clock,
        ),
        update_draft=UpdateMedicationHistoryDraftUseCase(
            record_repository, corporate_access
        ),
        finalize=FinalizeMedicationHistoryUseCase(
            record_repository,
            profile_repository,
            corporate_access,
            unit_of_work,
        ),
        amend=AmendMedicationHistoryUseCase(
            record_repository,
            corporate_access,
            counselor_qualification,
            counselor,
            clock,
        ),
        get=GetMedicationHistoryUseCase(record_repository, corporate_access),
        list_by_patient=ListMedicationHistoriesByPatientUseCase(
            record_repository, corporate_access
        ),
        get_medical_profile=GetPatientMedicalProfileUseCase(
            profile_repository, corporate_access
        ),
        rebuild_medical_profile=RebuildPatientMedicalProfileUseCase(
            record_repository, profile_repository, corporate_access
        ),
    )
