"""Applicationのregistryを定義する。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.care_event.commands.create_event import CreateEventUseCase
from app.application.care_event.commands.create_event_definition import (
    CreateEventDefinitionUseCase,
)
from app.application.care_event.commands.update_event_definition import (
    UpdateEventDefinitionUseCase,
)
from app.application.care_event.queries.get_event import GetEventUseCase
from app.application.care_event.queries.list_event_definitions import (
    ListEventDefinitionsUseCase,
)
from app.application.care_event.queries.list_related_event_candidates import (
    ListRelatedEventCandidatesUseCase,
)
from app.application.composition.commands.register_contract import (
    RegisterContractUseCase,
)
from app.application.corporate.commands.change_corporate_name import (
    ChangeCorporateNameUseCase,
)
from app.application.corporate.commands.change_corporate_status import (
    ChangeCorporateStatusUseCase,
)
from app.application.corporate.commands.change_representative import (
    ChangeRepresentativeUseCase,
)
from app.application.corporate.commands.register_corporate import (
    RegisterCorporateUseCase,
)
from app.application.corporate.commands.update_corporate_details import (
    UpdateCorporateDetailsUseCase,
)
from app.application.corporate.commands.update_corporate_policy import (
    UpdateCorporatePolicyUseCase,
)
from app.application.corporate.queries.get_corporate import GetCorporateUseCase
from app.application.corporate.queries.list_corporates import ListCorporatesUseCase
from app.application.coverage.commands.change_patient_coverage_period import (
    ChangePatientCoveragePeriodUseCase,
)
from app.application.coverage.commands.deactivate_patient_coverage import (
    DeactivatePatientCoverageUseCase,
)
from app.application.coverage.commands.record_coverage_selection import (
    RecordCoverageSelectionUseCase,
)
from app.application.coverage.commands.register_patient_coverage import (
    RegisterPatientCoverageUseCase,
)
from app.application.coverage.queries.get_last_coverage_selection import (
    GetLastCoverageSelectionUseCase,
)
from app.application.coverage.queries.get_patient_coverage import (
    GetPatientCoverageUseCase,
)
from app.application.coverage.queries.list_patient_coverages import (
    ListPatientCoveragesUseCase,
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
from app.application.identity.commands.change_membership import ChangeMembershipUseCase
from app.application.identity.commands.link_staff_person import LinkStaffPersonUseCase
from app.application.identity.commands.reactivate_account import (
    ReactivateAccountUseCase,
)
from app.application.identity.commands.register_person import RegisterPersonUseCase
from app.application.identity.commands.register_staff_for_admin import (
    RegisterStaffForAdminUseCase,
)
from app.application.identity.commands.suspend_account import SuspendAccountUseCase
from app.application.identity.queries.get_user import GetUserUseCase
from app.application.identity.queries.list_users import ListUsersUseCase
from app.application.identity.queries.resolve_actor import ResolveActorUseCase
from app.application.integration.commands.ingest_nsips import IngestNsipsUseCase
from app.application.integration.queries.get_nsips_source import (
    GetNsipsSourceUseCase,
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
from app.application.medication_history.queries.verify_statutory_record import (
    VerifyStatutoryRecordUseCase,
)
from app.application.medicine_catalog.commands.import_yj_catalog import (
    ImportYjCatalogUseCase,
)
from app.application.medicine_catalog.commands.register_medicine import (
    RegisterMedicineUseCase,
)
from app.application.medicine_catalog.queries.get_effective_medicine import (
    GetEffectiveMedicineUseCase,
)
from app.application.patient.commands.change_patient_birth_date import (
    ChangePatientBirthDateUseCase,
)
from app.application.patient.commands.change_patient_heading import (
    ChangePatientHeadingUseCase,
)
from app.application.patient.commands.change_patient_names import (
    ChangePatientNamesUseCase,
)
from app.application.patient.commands.change_patient_profile import (
    ChangePatientProfileUseCase,
)
from app.application.patient.commands.deactivate_patient import DeactivatePatientUseCase
from app.application.patient.commands.deactivate_patient_external_identifier import (
    DeactivatePatientExternalIdentifierUseCase,
)
from app.application.patient.commands.merge_patients import MergePatientsUseCase
from app.application.patient.commands.reactivate_patient import ReactivatePatientUseCase
from app.application.patient.commands.register_patient import RegisterPatientUseCase
from app.application.patient.commands.register_patient_external_identifier import (
    RegisterPatientExternalIdentifierUseCase,
)
from app.application.patient.queries.get_patient import GetPatientUseCase
from app.application.patient.queries.get_patient_external_identifier import (
    GetPatientExternalIdentifierUseCase,
)
from app.application.patient.queries.get_patient_heading import GetPatientHeadingUseCase
from app.application.patient.queries.list_patient_external_identifiers import (
    ListPatientExternalIdentifiersUseCase,
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
from app.application.reception.commands.associate_reception_medication_history import (
    AssociateReceptionMedicationHistoryUseCase,
)
from app.application.staff.commands.activate_staff import ActivateStaffUseCase
from app.application.staff.commands.assign_staff_concurrent_store import (
    AssignStaffConcurrentStoreUseCase,
)
from app.application.staff.commands.change_staff_job_title import (
    ChangeStaffJobTitleUseCase,
)
from app.application.staff.commands.change_staff_names import ChangeStaffNamesUseCase
from app.application.staff.commands.deactivate_staff import DeactivateStaffUseCase
from app.application.staff.commands.manage_staff_leave import (
    ReturnStaffFromLeaveUseCase,
    StartStaffLeaveUseCase,
)
from app.application.staff.commands.register_staff import RegisterStaffUseCase
from app.application.staff.commands.remove_staff_concurrent_store import (
    RemoveStaffConcurrentStoreUseCase,
)
from app.application.staff.commands.transfer_staff_home_store import (
    TransferStaffHomeStoreUseCase,
)
from app.application.staff.commands.update_staff_employment import (
    UpdateStaffEmploymentUseCase,
)
from app.application.staff.commands.update_staff_qualifications import (
    UpdateStaffQualificationsUseCase,
)
from app.application.staff.queries.get_staff import GetStaffUseCase
from app.application.staff.queries.list_staffs import ListStaffsUseCase
from app.application.store.commands.change_insurance_pharmacy_number import (
    ChangeInsurancePharmacyNumberUseCase,
)
from app.application.store.commands.change_store_address import (
    ChangeStoreAddressUseCase,
)
from app.application.store.commands.change_store_business_hours import (
    ChangeStoreBusinessHoursUseCase,
)
from app.application.store.commands.change_store_code import ChangeStoreCodeUseCase
from app.application.store.commands.change_store_contact_info import (
    ChangeStoreContactInfoUseCase,
)
from app.application.store.commands.change_store_names import ChangeStoreNamesUseCase
from app.application.store.commands.change_store_status import ChangeStoreStatusUseCase
from app.application.store.commands.manage_safety_manager import (
    AppointSafetyManagerUseCase,
    RemoveSafetyManagerUseCase,
)
from app.application.store.commands.manage_store_manager import (
    ManageStoreManagerUseCase,
)
from app.application.store.commands.register_store import RegisterStoreUseCase
from app.application.store.commands.revoke_store_closure import (
    RevokeStoreClosureUseCase,
)
from app.application.store.commands.update_certifications import (
    UpdateCertificationsUseCase,
)
from app.application.store.commands.update_licenses import (
    UpdateStoreLicensesUseCase,
)
from app.application.store.commands.update_public_expense_designations import (
    UpdatePublicExpenseDesignationsUseCase,
)
from app.application.store.commands.update_store_policy import (
    UpdateStorePolicyUseCase,
)
from app.application.store.queries.get_effective_policy import (
    GetEffectivePolicyUseCase,
)
from app.application.store.queries.get_store import GetStoreUseCase
from app.application.store.queries.get_store_opening_status import (
    GetStoreOpeningStatusUseCase,
)
from app.application.store.queries.list_stores import ListStoresUseCase


@dataclass(frozen=True, slots=True)
class CareEventUseCases:
    """業務Eventコンテキストの操作一式。"""

    create: CreateEventUseCase
    get: GetEventUseCase
    create_definition: CreateEventDefinitionUseCase
    list_definitions: ListEventDefinitionsUseCase
    update_definition: UpdateEventDefinitionUseCase
    list_related_candidates: ListRelatedEventCandidatesUseCase


@dataclass(frozen=True, slots=True)
class PrescriptionUseCases:
    """処方箋コンテキストのユースケース。"""

    register: RegisterPrescriptionUseCase
    get: GetPrescriptionUseCase
    ready_for_dispensing: ReadyForDispensingUseCase
    cancel: CancelPrescriptionUseCase
    start_inquiry: StartInquiryUseCase
    resolve_inquiry: ResolveInquiryUseCase
    audit_interactions: AuditDrugInteractionsUseCase


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


@dataclass(frozen=True, slots=True)
class MedicationHistoryUseCases:
    """薬歴コンテキストのユースケース。"""

    start: StartMedicationHistoryUseCase
    update_draft: UpdateMedicationHistoryDraftUseCase
    finalize: FinalizeMedicationHistoryUseCase
    amend: AmendMedicationHistoryUseCase
    correct_fact: CorrectMedicationHistoryFactUseCase
    get: GetMedicationHistoryUseCase
    get_follow_up_source: GetFollowUpSourceUseCase
    list_by_patient: ListMedicationHistoriesByPatientUseCase
    get_medical_profile: GetPatientMedicalProfileUseCase
    rebuild_medical_profile: RebuildPatientMedicalProfileUseCase
    verify_statutory_record: VerifyStatutoryRecordUseCase
    get_category_catalog: EnsureCategoryCatalogUseCase
    update_category_catalog: UpdateCategoryCatalogUseCase
    record_tracing_report: RecordTracingReportUseCase
    record_tracing_report_response: RecordTracingReportResponseUseCase
    get_view: GetMedicationHistoryViewUseCase
    list_external_corrections: ListPendingExternalCorrectionsUseCase
    review_external_correction: ReviewExternalPrescriptionCorrectionUseCase


@dataclass(frozen=True, slots=True)
class IdentityUseCases:
    """本人・アカウント管理と最新の権限解決。"""

    register_contract: RegisterContractUseCase
    register_person: RegisterPersonUseCase
    link_staff: LinkStaffPersonUseCase
    change_membership: ChangeMembershipUseCase
    list_users: ListUsersUseCase
    get_user: GetUserUseCase
    suspend_account: SuspendAccountUseCase
    reactivate_account: ReactivateAccountUseCase
    resolve_actor: ResolveActorUseCase
    register_staff_for_admin: RegisterStaffForAdminUseCase


@dataclass(frozen=True, slots=True)
class IntegrationUseCases:
    """外部連携コンテキストのユースケース一覧。"""

    ingest_nsips: IngestNsipsUseCase
    get_nsips_source: GetNsipsSourceUseCase


@dataclass(frozen=True, slots=True)
class MedicineCatalogUseCases:
    """医薬品マスタコンテキストのユースケース。"""

    register: RegisterMedicineUseCase
    get_effective: GetEffectiveMedicineUseCase
    import_yj: ImportYjCatalogUseCase


@dataclass(frozen=True, slots=True)
class CorporateUseCases:
    """法人コンテキストのユースケース。"""

    register: RegisterCorporateUseCase
    list: ListCorporatesUseCase
    get: GetCorporateUseCase
    change_name: ChangeCorporateNameUseCase
    change_representative: ChangeRepresentativeUseCase
    change_status: ChangeCorporateStatusUseCase
    update_policy: UpdateCorporatePolicyUseCase
    update_details: UpdateCorporateDetailsUseCase


@dataclass(frozen=True, slots=True)
class StoreUseCases:
    """店舗コンテキストのユースケース。"""

    register: RegisterStoreUseCase
    change_status: ChangeStoreStatusUseCase
    revoke_closure: RevokeStoreClosureUseCase
    manage_manager: ManageStoreManagerUseCase
    get: GetStoreUseCase
    list_by_corporate: ListStoresUseCase
    change_names: ChangeStoreNamesUseCase
    change_code: ChangeStoreCodeUseCase
    change_address: ChangeStoreAddressUseCase
    change_contact_info: ChangeStoreContactInfoUseCase
    change_insurance_pharmacy_number: ChangeInsurancePharmacyNumberUseCase
    change_business_hours: ChangeStoreBusinessHoursUseCase
    opening_status: GetStoreOpeningStatusUseCase
    update_licenses: UpdateStoreLicensesUseCase
    update_policy: UpdateStorePolicyUseCase
    effective_policy: GetEffectivePolicyUseCase
    update_certifications: UpdateCertificationsUseCase
    update_public_expense_designations: UpdatePublicExpenseDesignationsUseCase
    appoint_safety_manager: AppointSafetyManagerUseCase
    remove_safety_manager: RemoveSafetyManagerUseCase


@dataclass(frozen=True, slots=True)
class StaffUseCases:
    """スタッフコンテキストのユースケース。"""

    register: RegisterStaffUseCase
    get: GetStaffUseCase
    list_by_corporate: ListStaffsUseCase
    change_names: ChangeStaffNamesUseCase
    change_job_title: ChangeStaffJobTitleUseCase
    update_qualifications: UpdateStaffQualificationsUseCase
    transfer_home_store: TransferStaffHomeStoreUseCase
    assign_concurrent_store: AssignStaffConcurrentStoreUseCase
    remove_concurrent_store: RemoveStaffConcurrentStoreUseCase
    activate: ActivateStaffUseCase
    deactivate: DeactivateStaffUseCase
    update_employment: UpdateStaffEmploymentUseCase
    start_leave: StartStaffLeaveUseCase
    return_from_leave: ReturnStaffFromLeaveUseCase


@dataclass(frozen=True, slots=True)
class PatientUseCases:
    """患者コンテキストのユースケース。"""

    register: RegisterPatientUseCase
    get: GetPatientUseCase
    change_names: ChangePatientNamesUseCase
    change_birth_date: ChangePatientBirthDateUseCase
    deactivate: DeactivatePatientUseCase
    reactivate: ReactivatePatientUseCase
    merge: MergePatientsUseCase
    register_external_identifier: RegisterPatientExternalIdentifierUseCase
    get_external_identifier: GetPatientExternalIdentifierUseCase
    list_external_identifiers: ListPatientExternalIdentifiersUseCase
    deactivate_external_identifier: DeactivatePatientExternalIdentifierUseCase
    change_profile: ChangePatientProfileUseCase
    get_heading: GetPatientHeadingUseCase
    change_heading: ChangePatientHeadingUseCase


@dataclass(frozen=True, slots=True)
class CoverageUseCases:
    """資格台帳コンテキストのユースケース。"""

    register: RegisterPatientCoverageUseCase
    get: GetPatientCoverageUseCase
    list_by_patient: ListPatientCoveragesUseCase
    change_period: ChangePatientCoveragePeriodUseCase
    deactivate: DeactivatePatientCoverageUseCase
    record_coverage_selection: RecordCoverageSelectionUseCase
    get_last_coverage_selection: GetLastCoverageSelectionUseCase


@dataclass(frozen=True, slots=True)
class ReceptionUseCases:
    """受付コンテキストのユースケース。"""

    associate_medication_history: AssociateReceptionMedicationHistoryUseCase
