"""処方箋・調剤・薬歴のユースケース束。

受付後の臨床の流れで連なる3コンテキストをまとめる。参照Boundaryの実アダプタを
多く要し、複数集約を書くユースケースは ``UnitOfWork`` を必須依存として受け取る。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.common.clock import Clock
from app.application.composition.dispensing_references import (
    DispensingStaffQualificationAdapter,
    DispensingStoreReferenceAdapter,
    PrescriptionSourceAdapter,
)
from app.application.composition.medication_history_references import (
    CounselorQualificationAdapter,
    DispensingSourceAdapter,
    MedicationHistoryStoreReferenceAdapter,
)
from app.application.composition.medicine_restriction_adapter import (
    MedicineCatalogRestrictionAdapter,
)
from app.application.composition.prescription_references import (
    CoverageSelectionPublicExpenseAdapter,
    PrescriptionPatientReferenceAdapter,
    PrescriptionStaffQualificationAdapter,
    PrescriptionStoreReferenceAdapter,
)
from app.application.corporate.corporate_access import CorporateAccessService
from app.application.dispensing.complete_dispensing import CompleteDispensingUseCase
from app.application.dispensing.get_dispensing import GetDispensingUseCase
from app.application.dispensing.list_dispensings_by_prescription import (
    ListDispensingsByPrescriptionUseCase,
)
from app.application.dispensing.record_audit import RecordAuditUseCase
from app.application.dispensing.record_dispensed_content import (
    RecordDispensedContentUseCase,
)
from app.application.dispensing.start_dispensing import StartDispensingUseCase
from app.application.dispensing.verify_dispensing import VerifyDispensingUseCase
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
from app.application.prescription.cancel_prescription import CancelPrescriptionUseCase
from app.application.prescription.get_prescription import GetPrescriptionUseCase
from app.application.prescription.ready_for_dispensing import ReadyForDispensingUseCase
from app.application.prescription.register_prescription import (
    RegisterPrescriptionUseCase,
)
from app.application.prescription.resolve_inquiry import ResolveInquiryUseCase
from app.application.prescription.start_inquiry import StartInquiryUseCase
from app.domain.dispensing.services import (
    DispensingConsistencyService,
    DispensingIterationUniquenessService,
    DispensingPharmacistService,
)
from app.domain.medication_history.services import CounselorQualificationService
from app.domain.prescription.services import (
    InquiryPharmacistService,
    NarcoticPrescriptionService,
    PrescriptionDocumentNumberUniquenessService,
    PublicExpenseBurdenService,
    RefillEligibilityService,
)
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.infrastructure.postgres.repositories import PostgresRepositorySet

# --------------------------------------------------------------------------
# 処方箋
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PrescriptionUseCases:
    """処方箋コンテキストのユースケース。"""

    register: RegisterPrescriptionUseCase
    get: GetPrescriptionUseCase
    ready_for_dispensing: ReadyForDispensingUseCase
    cancel: CancelPrescriptionUseCase
    start_inquiry: StartInquiryUseCase
    resolve_inquiry: ResolveInquiryUseCase


def build_prescription_use_cases(
    repositories: PostgresRepositorySet,
    corporate_access: CorporateAccessService,
    clock: Clock,
) -> PrescriptionUseCases:
    """処方箋ユースケースを組み立てる。"""
    repository = repositories.prescription
    return PrescriptionUseCases(
        register=RegisterPrescriptionUseCase(
            repository,
            corporate_access,
            PrescriptionStoreReferenceAdapter(repositories.store),
            PrescriptionPatientReferenceAdapter(repositories.patient),
            MedicineCatalogRestrictionAdapter(repositories.medicine_catalog),
            CoverageSelectionPublicExpenseAdapter(
                repositories.coverage_selection_record
            ),
            PrescriptionDocumentNumberUniquenessService(),
            NarcoticPrescriptionService(),
            RefillEligibilityService(),
            PublicExpenseBurdenService(),
        ),
        get=GetPrescriptionUseCase(repository, corporate_access),
        ready_for_dispensing=ReadyForDispensingUseCase(repository, corporate_access),
        cancel=CancelPrescriptionUseCase(repository, corporate_access),
        start_inquiry=StartInquiryUseCase(
            repository,
            corporate_access,
            PrescriptionStaffQualificationAdapter(repositories.staff),
            InquiryPharmacistService(),
            clock,
        ),
        resolve_inquiry=ResolveInquiryUseCase(repository, corporate_access, clock),
    )


# --------------------------------------------------------------------------
# 調剤
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DispensingUseCases:
    """調剤コンテキストのユースケース。"""

    start: StartDispensingUseCase
    record_dispensed_content: RecordDispensedContentUseCase
    verify: VerifyDispensingUseCase
    record_audit: RecordAuditUseCase
    complete: CompleteDispensingUseCase
    get: GetDispensingUseCase
    list_by_prescription: ListDispensingsByPrescriptionUseCase


def build_dispensing_use_cases(
    repositories: PostgresRepositorySet,
    corporate_access: CorporateAccessService,
    clock: Clock,
    unit_of_work: PostgresUnitOfWork,
) -> DispensingUseCases:
    """調剤ユースケースを組み立てる。

    処方箋の参照と調剤済への遷移は**同じアダプタ・同じRepositoryインスタンス**が
    担う。読みと書きで別のRepositoryを渡すと、Unit of Work が覚えている世代と
    書き込みが噛み合わなくなる。
    """
    repository = repositories.dispensing
    prescription_source = PrescriptionSourceAdapter(repositories.prescription)
    staff_qualification = DispensingStaffQualificationAdapter(repositories.staff)
    consistency = DispensingConsistencyService()
    pharmacist = DispensingPharmacistService()
    return DispensingUseCases(
        start=StartDispensingUseCase(
            repository,
            corporate_access,
            DispensingStoreReferenceAdapter(repositories.store),
            prescription_source,
            staff_qualification,
            consistency,
            pharmacist,
            DispensingIterationUniquenessService(),
            clock,
        ),
        record_dispensed_content=RecordDispensedContentUseCase(
            repository, corporate_access, prescription_source, consistency
        ),
        verify=VerifyDispensingUseCase(
            repository, corporate_access, staff_qualification, pharmacist, clock
        ),
        record_audit=RecordAuditUseCase(
            repository, corporate_access, staff_qualification, pharmacist, clock
        ),
        complete=CompleteDispensingUseCase(
            repository,
            corporate_access,
            prescription_source,
            unit_of_work,
        ),
        get=GetDispensingUseCase(repository, corporate_access),
        list_by_prescription=ListDispensingsByPrescriptionUseCase(
            repository, corporate_access
        ),
    )


# --------------------------------------------------------------------------
# 薬歴
# --------------------------------------------------------------------------


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


__all__ = [
    "DispensingUseCases",
    "MedicationHistoryUseCases",
    "PrescriptionUseCases",
    "build_dispensing_use_cases",
    "build_medication_history_use_cases",
    "build_prescription_use_cases",
]
