"""処方箋・調剤・薬歴のユースケース束。

受付後の臨床の流れで連なる3コンテキストをまとめる。参照Boundaryの実アダプタを
多く要し、複数集約を書くユースケースは ``UnitOfWork`` を必須依存として受け取る。"""

from __future__ import annotations

from app.application.access_control.policies import AuthorizationService
from app.application.common.clock import Clock
from app.application.common.organization_lock import OrganizationLock
from app.application.composition.adapters.care_event_references import (
    MedicationHistoryEventReferenceAdapter,
)
from app.application.composition.adapters.dispensing_references import (
    DispensingStaffQualificationAdapter,
    DispensingStoreReferenceAdapter,
    PrescriptionSourceAdapter,
)
from app.application.composition.adapters.medication_history_patient_profile import (
    MedicationHistoryPatientProfileAdapter,
)
from app.application.composition.adapters.medication_history_references import (
    CounselorQualificationAdapter,
    DispensingSourceAdapter,
    MedicationHistoryEventOccurrenceAdapter,
    MedicationHistoryStoreReferenceAdapter,
    ReceptionMedicationHistorySourceAdapter,
    StatutoryRecordSourceAdapter,
)
from app.application.composition.adapters.medicine_restriction_adapter import (
    MedicineCatalogRestrictionAdapter,
)
from app.application.composition.adapters.prescription_references import (
    CoverageSelectionPublicExpenseAdapter,
    PrescriptionPatientReferenceAdapter,
    PrescriptionStaffQualificationAdapter,
    PrescriptionStoreReferenceAdapter,
)
from app.application.composition.adapters.store_operation_adapter import (
    StoreOperationAdapter,
)
from app.application.composition.registry import (
    DispensingUseCases,
    MedicationHistoryUseCases,
    PrescriptionUseCases,
)
from app.application.corporate.commands.services.corporate_access import (
    CorporateAccessService,
)
from app.application.dispensing.commands.complete_dispensing import (
    CompleteDispensingUseCase,
)
from app.application.dispensing.commands.record_audit import RecordAuditUseCase
from app.application.dispensing.commands.record_dispensed_content import (
    RecordDispensedContentUseCase,
)
from app.application.dispensing.commands.start_dispensing import StartDispensingUseCase
from app.application.dispensing.commands.verify_dispensing import (
    VerifyDispensingUseCase,
)
from app.application.dispensing.queries.get_dispensing import GetDispensingUseCase
from app.application.dispensing.queries.list_dispensings_by_prescription import (
    ListDispensingsByPrescriptionUseCase,
)
from app.application.medication_history.commands.amend_medication_history import (
    AmendMedicationHistoryUseCase,
)
from app.application.medication_history.commands.correct_medication_history_fact import (
    CorrectMedicationHistoryFactUseCase,
)
from app.application.medication_history.commands.ensure_category_catalog import (
    EnsureCategoryCatalogUseCase,
)
from app.application.medication_history.commands.finalize_medication_history import (
    FinalizeMedicationHistoryUseCase,
)
from app.application.medication_history.commands.rebuild_patient_medical_profile import (
    RebuildPatientMedicalProfileUseCase,
)
from app.application.medication_history.commands.record_tracing_report import (
    RecordTracingReportUseCase,
)
from app.application.medication_history.commands.record_tracing_report_response import (
    RecordTracingReportResponseUseCase,
)
from app.application.medication_history.commands.review_external_prescription_correction import (
    ReviewExternalPrescriptionCorrectionUseCase,
)
from app.application.medication_history.commands.services.profile_projection_service import (
    PatientMedicalProfileProjectionService,
)
from app.application.medication_history.commands.start_medication_history import (
    StartMedicationHistoryUseCase,
)
from app.application.medication_history.commands.update_category_catalog import (
    UpdateCategoryCatalogUseCase,
)
from app.application.medication_history.commands.update_medication_history_draft import (
    UpdateMedicationHistoryDraftUseCase,
)
from app.application.medication_history.queries.get_follow_up_source import (
    GetFollowUpSourceUseCase,
)
from app.application.medication_history.queries.get_medication_history import (
    GetMedicationHistoryUseCase,
)
from app.application.medication_history.queries.get_medication_history_view import (
    GetMedicationHistoryViewUseCase,
)
from app.application.medication_history.queries.get_patient_medical_profile import (
    GetPatientMedicalProfileUseCase,
)
from app.application.medication_history.queries.list_medication_histories_by_patient import (
    ListMedicationHistoriesByPatientUseCase,
)
from app.application.medication_history.queries.list_pending_external_corrections import (
    ListPendingExternalCorrectionsUseCase,
)
from app.application.medication_history.queries.services.statutory_projection import (
    StatutoryProjectionService,
)
from app.application.medication_history.queries.verify_statutory_record import (
    VerifyStatutoryRecordUseCase,
)
from app.application.prescription.commands.audit_drug_interactions import (
    AuditDrugInteractionsUseCase,
)
from app.application.prescription.commands.cancel_prescription import (
    CancelPrescriptionUseCase,
)
from app.application.prescription.commands.ready_for_dispensing import (
    ReadyForDispensingUseCase,
)
from app.application.prescription.commands.register_prescription import (
    RegisterPrescriptionUseCase,
)
from app.application.prescription.commands.resolve_inquiry import ResolveInquiryUseCase
from app.application.prescription.commands.start_inquiry import StartInquiryUseCase
from app.application.prescription.queries.get_prescription import GetPrescriptionUseCase
from app.domain.dispensing.services import (
    DispensingConsistencyService,
    DispensingIterationUniquenessService,
    DispensingPharmacistService,
)
from app.domain.medication_history.services import (
    CounselorQualificationService,
    StatutoryDispensingRecordService,
)
from app.domain.prescription.repositories import DrugInteractionDataSource
from app.domain.prescription.services import (
    InquiryPharmacistService,
    NarcoticPrescriptionService,
    PrescriptionDocumentNumberUniquenessService,
    PublicExpenseBurdenService,
    RefillEligibilityService,
)
from app.infrastructure.di.repositories import (
    PostgresRepositorySet,
)
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.infrastructure.postgres.organization_lock import PostgresOrganizationLock
from app.infrastructure.prescription.external.drug_interaction import (
    BlackBoxDrugInteractionDataSource,
)
from app.infrastructure.readers.dispensing_get_dispensing import GetDispensingProjection
from app.infrastructure.readers.dispensing_list_dispensings_by_prescription import (
    ListDispensingsByPrescriptionProjection,
)
from app.infrastructure.readers.medication_history_get_follow_up_source import (
    GetFollowUpSourceProjection,
)
from app.infrastructure.readers.medication_history_get_medication_history import (
    GetMedicationHistoryProjection,
)
from app.infrastructure.readers.medication_history_get_medication_history_view import (
    GetMedicationHistoryViewProjection,
)
from app.infrastructure.readers.medication_history_get_patient_medical_profile import (
    GetPatientMedicalProfileProjection,
)
from app.infrastructure.readers.medication_history_list_medication_histories_by_patient import (
    ListMedicationHistoriesByPatientProjection,
)
from app.infrastructure.readers.medication_history_list_pending_external_corrections import (
    ListPendingExternalCorrectionsProjection,
)
from app.infrastructure.readers.medication_history_verify_statutory_record import (
    VerifyStatutoryRecordProjection,
)
from app.infrastructure.readers.prescription_get_prescription import (
    GetPrescriptionProjection,
)

# --------------------------------------------------------------------------
# 処方箋
# --------------------------------------------------------------------------


def build_prescription_use_cases(
    repositories: PostgresRepositorySet,
    corporate_access: CorporateAccessService,
    clock: Clock,
    *,
    interaction_data_source: DrugInteractionDataSource | None = None,
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
        get=GetPrescriptionUseCase(
            reader=GetPrescriptionProjection(repository),
            corporate_access=corporate_access,
        ),
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
        audit_interactions=AuditDrugInteractionsUseCase(
            authorization_service=AuthorizationService(corporate_access.actor),
            data_source=interaction_data_source or BlackBoxDrugInteractionDataSource(),
        ),
    )


# --------------------------------------------------------------------------
# 調剤
# --------------------------------------------------------------------------


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
            clock,
        ),
        get=GetDispensingUseCase(
            reader=GetDispensingProjection(repository),
            corporate_access=corporate_access,
        ),
        list_by_prescription=ListDispensingsByPrescriptionUseCase(
            reader=ListDispensingsByPrescriptionProjection(repository),
            corporate_access=corporate_access,
        ),
    )


# --------------------------------------------------------------------------
# 薬歴
# --------------------------------------------------------------------------


def build_medication_history_use_cases(
    repositories: PostgresRepositorySet,
    corporate_access: CorporateAccessService,
    clock: Clock,
    unit_of_work: PostgresUnitOfWork,
    *,
    organization_lock: OrganizationLock | None = None,
) -> MedicationHistoryUseCases:
    """薬歴ユースケースを組み立てる。

    確定と再構築は薬歴と頭書きの2集約へ書く。どちらも同じスコープの
    トランザクションに入るので、頭書きだけが取り残されることはない。
    """
    record_repository = repositories.medication_history
    profile_repository = repositories.patient_medical_profile
    catalog_repository = repositories.medication_history_category_catalog
    counselor_qualification = CounselorQualificationAdapter(repositories.staff)
    counselor = CounselorQualificationService()
    dispensing_source = DispensingSourceAdapter(repositories.dispensing)
    store_operations = StoreOperationAdapter(
        repositories.store,
        corporate_access,
        repositories.manager_assignment,
        clock,
    )
    actual_lock = organization_lock or PostgresOrganizationLock(unit_of_work)
    projection_service = PatientMedicalProfileProjectionService(
        record_repository=record_repository,
        profile_repository=profile_repository,
    )
    return MedicationHistoryUseCases(
        start=StartMedicationHistoryUseCase(
            record_repository,
            corporate_access,
            MedicationHistoryStoreReferenceAdapter(repositories.store),
            dispensing_source,
            counselor_qualification,
            counselor,
            unit_of_work,
            event_reference=MedicationHistoryEventReferenceAdapter(repositories.event),
            store_operations=store_operations,
            clock=clock,
            reception_source=ReceptionMedicationHistorySourceAdapter(
                repositories.reception
            ),
        ),
        update_draft=UpdateMedicationHistoryDraftUseCase(
            record_repository, corporate_access
        ),
        finalize=FinalizeMedicationHistoryUseCase(
            record_repository,
            profile_repository,
            corporate_access,
            unit_of_work,
            organization_lock=actual_lock,
            category_catalog_repository=catalog_repository,
            staff_qualification=counselor_qualification,
            counselor_service=counselor,
            clock=clock,
            event_occurrence=MedicationHistoryEventOccurrenceAdapter(
                repositories.event
            ),
            projection_service=projection_service,
        ),
        amend=AmendMedicationHistoryUseCase(
            record_repository,
            corporate_access,
            counselor_qualification,
            counselor,
            clock,
        ),
        correct_fact=CorrectMedicationHistoryFactUseCase(
            record_repository=record_repository,
            profile_repository=profile_repository,
            corporate_access=corporate_access,
            unit_of_work=unit_of_work,
            organization_lock=actual_lock,
            staff_qualification=counselor_qualification,
            counselor_service=counselor,
            category_catalog_repository=catalog_repository,
            store_operations=store_operations,
            clock=clock,
            projection_service=projection_service,
        ),
        get=GetMedicationHistoryUseCase(
            reader=GetMedicationHistoryProjection(
                record_repository,
                MedicationHistoryEventReferenceAdapter(repositories.event),
            ),
            corporate_access=corporate_access,
        ),
        get_follow_up_source=GetFollowUpSourceUseCase(
            reader=GetFollowUpSourceProjection(record_repository),
            corporate_access=corporate_access,
        ),
        list_by_patient=ListMedicationHistoriesByPatientUseCase(
            reader=ListMedicationHistoriesByPatientProjection(
                record_repository,
                MedicationHistoryEventReferenceAdapter(repositories.event),
            ),
            corporate_access=corporate_access,
        ),
        get_medical_profile=GetPatientMedicalProfileUseCase(
            reader=GetPatientMedicalProfileProjection(profile_repository),
            corporate_access=corporate_access,
        ),
        rebuild_medical_profile=RebuildPatientMedicalProfileUseCase(
            record_repository,
            profile_repository,
            corporate_access,
            unit_of_work,
            organization_lock=actual_lock,
            projection_service=projection_service,
        ),
        verify_statutory_record=VerifyStatutoryRecordUseCase(
            reader=VerifyStatutoryRecordProjection(
                record_repository,
                dispensing_source,
                StatutoryRecordSourceAdapter(
                    repositories.patient, repositories.prescription, repositories.staff
                ),
                StatutoryProjectionService(StatutoryDispensingRecordService()),
            ),
            corporate_access=corporate_access,
        ),
        get_category_catalog=EnsureCategoryCatalogUseCase(
            catalog_repository,
            corporate_access,
        ),
        update_category_catalog=UpdateCategoryCatalogUseCase(
            catalog_repository,
            corporate_access,
        ),
        record_tracing_report=RecordTracingReportUseCase(
            record_repository,
            corporate_access,
            counselor_qualification,
            counselor,
        ),
        record_tracing_report_response=RecordTracingReportResponseUseCase(
            record_repository,
            corporate_access,
        ),
        get_view=GetMedicationHistoryViewUseCase(
            reader=GetMedicationHistoryViewProjection(
                record_repository,
                MedicationHistoryPatientProfileAdapter(repositories.patient),
            ),
            corporate_access=corporate_access,
        ),
        list_external_corrections=ListPendingExternalCorrectionsUseCase(
            reader=ListPendingExternalCorrectionsProjection(record_repository),
            corporate_access=corporate_access,
        ),
        review_external_correction=ReviewExternalPrescriptionCorrectionUseCase(
            record_repository,
            corporate_access,
            counselor_qualification,
            repositories.prescription,
            clock,
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
