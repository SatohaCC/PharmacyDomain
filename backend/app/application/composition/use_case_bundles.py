"""リクエスト境界へ公開するApplicationのユースケース束。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.care_event.create_event import CreateEventUseCase
from app.application.care_event.event_definition import (
    CreateEventDefinitionUseCase,
    ListEventDefinitionsUseCase,
    UpdateEventDefinitionUseCase,
)
from app.application.care_event.get_event import GetEventUseCase
from app.application.care_event.list_related_candidates import (
    ListRelatedEventCandidatesUseCase,
)
from app.application.corporate.change_corporate_name import ChangeCorporateNameUseCase
from app.application.corporate.change_corporate_status import (
    ChangeCorporateStatusUseCase,
)
from app.application.corporate.change_representative import ChangeRepresentativeUseCase
from app.application.corporate.get_corporate import GetCorporateUseCase
from app.application.corporate.list_corporates import ListCorporatesUseCase
from app.application.corporate.register_corporate import RegisterCorporateUseCase
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
from app.application.identity.accept_invitation import AcceptInvitationUseCase
from app.application.identity.cancel_invitation import CancelInvitationUseCase
from app.application.identity.change_account_status import (
    ReactivateAccountUseCase,
    SuspendAccountUseCase,
)
from app.application.identity.change_membership import ChangeMembershipUseCase
from app.application.identity.get_invitation import GetInvitationUseCase
from app.application.identity.get_user import GetUserUseCase
from app.application.identity.invite_user import InviteUserUseCase
from app.application.identity.link_staff import LinkStaffPersonUseCase
from app.application.identity.list_users import ListUsersUseCase
from app.application.identity.register_person import RegisterPersonUseCase
from app.application.identity.resolve_actor import ResolveActorUseCase
from app.application.integration.nsips.ingest_nsips import IngestNsipsUseCase
from app.application.medication_history.amend_medication_history import (
    AmendMedicationHistoryUseCase,
)
from app.application.medication_history.category_catalog import (
    GetCategoryCatalogUseCase,
    UpdateCategoryCatalogUseCase,
)
from app.application.medication_history.correct_medication_history_fact import (
    CorrectMedicationHistoryFactUseCase,
)
from app.application.medication_history.finalize_medication_history import (
    FinalizeMedicationHistoryUseCase,
)
from app.application.medication_history.get_medication_history import (
    GetFollowUpSourceUseCase,
    GetMedicationHistoryUseCase,
    ListMedicationHistoriesByPatientUseCase,
)
from app.application.medication_history.get_medication_history_view import (
    GetMedicationHistoryViewUseCase,
)
from app.application.medication_history.get_patient_medical_profile import (
    GetPatientMedicalProfileUseCase,
    RebuildPatientMedicalProfileUseCase,
)
from app.application.medication_history.list_pending_external_corrections import (
    ListPendingExternalCorrectionsUseCase,
)
from app.application.medication_history.record_tracing_report import (
    RecordTracingReportUseCase,
)
from app.application.medication_history.record_tracing_report_response import (
    RecordTracingReportResponseUseCase,
)
from app.application.medication_history.review_external_prescription_correction import (
    ReviewExternalPrescriptionCorrectionUseCase,
)
from app.application.medication_history.start_medication_history import (
    StartMedicationHistoryUseCase,
)
from app.application.medication_history.update_medication_history_draft import (
    UpdateMedicationHistoryDraftUseCase,
)
from app.application.medication_history.verify_statutory_record import (
    VerifyStatutoryRecordUseCase,
)
from app.application.medicine_catalog.get_medicine import GetEffectiveMedicineUseCase
from app.application.medicine_catalog.import_yj_catalog import ImportYjCatalogUseCase
from app.application.medicine_catalog.register_medicine import RegisterMedicineUseCase
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
from app.application.prescription.audit_interactions import (
    AuditDrugInteractionsUseCase,
)
from app.application.prescription.cancel_prescription import CancelPrescriptionUseCase
from app.application.prescription.get_prescription import GetPrescriptionUseCase
from app.application.prescription.ready_for_dispensing import ReadyForDispensingUseCase
from app.application.prescription.register_prescription import (
    RegisterPrescriptionUseCase,
)
from app.application.prescription.resolve_inquiry import ResolveInquiryUseCase
from app.application.prescription.start_inquiry import StartInquiryUseCase
from app.application.reception.associate_reception_medication_history import (
    AssociateReceptionMedicationHistoryUseCase,
)
from app.application.staff.activate_staff import ActivateStaffUseCase
from app.application.staff.assign_concurrent_store import (
    AssignStaffConcurrentStoreUseCase,
)
from app.application.staff.change_staff_job_title import ChangeStaffJobTitleUseCase
from app.application.staff.change_staff_names import ChangeStaffNamesUseCase
from app.application.staff.deactivate_staff import DeactivateStaffUseCase
from app.application.staff.get_staff import GetStaffUseCase
from app.application.staff.list_staffs import ListStaffsUseCase
from app.application.staff.register_staff import RegisterStaffUseCase
from app.application.staff.remove_concurrent_store import (
    RemoveStaffConcurrentStoreUseCase,
)
from app.application.staff.transfer_home_store import TransferStaffHomeStoreUseCase
from app.application.staff.update_qualifications import UpdateStaffQualificationsUseCase
from app.application.store.business_hours import (
    ChangeStoreBusinessHoursUseCase,
    GetStoreOpeningStatusUseCase,
)
from app.application.store.change_insurance_pharmacy_number import (
    ChangeInsurancePharmacyNumberUseCase,
)
from app.application.store.change_store_address import ChangeStoreAddressUseCase
from app.application.store.change_store_code import ChangeStoreCodeUseCase
from app.application.store.change_store_contact_info import (
    ChangeStoreContactInfoUseCase,
)
from app.application.store.change_store_name import ChangeStoreNamesUseCase
from app.application.store.get_store import GetStoreUseCase
from app.application.store.list_stores import ListStoresUseCase
from app.application.store.management import (
    ChangeStoreStatusUseCase,
    ManageStoreManagerUseCase,
    RevokeStoreClosureUseCase,
)
from app.application.store.register_store import RegisterStoreUseCase


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
    get_category_catalog: GetCategoryCatalogUseCase
    update_category_catalog: UpdateCategoryCatalogUseCase
    record_tracing_report: RecordTracingReportUseCase
    record_tracing_report_response: RecordTracingReportResponseUseCase
    get_view: GetMedicationHistoryViewUseCase
    list_external_corrections: ListPendingExternalCorrectionsUseCase
    review_external_correction: ReviewExternalPrescriptionCorrectionUseCase


@dataclass(frozen=True, slots=True)
class IdentityUseCases:
    """本人・アカウント管理と最新の権限解決。"""

    register_person: RegisterPersonUseCase
    link_staff: LinkStaffPersonUseCase
    invite: InviteUserUseCase
    accept: AcceptInvitationUseCase
    cancel_invitation: CancelInvitationUseCase
    get_invitation: GetInvitationUseCase
    change_membership: ChangeMembershipUseCase
    list_users: ListUsersUseCase
    get_user: GetUserUseCase
    suspend_account: SuspendAccountUseCase
    reactivate_account: ReactivateAccountUseCase
    resolve_actor: ResolveActorUseCase


@dataclass(frozen=True, slots=True)
class IntegrationUseCases:
    """外部連携コンテキストのユースケース一覧。"""

    ingest_nsips: IngestNsipsUseCase


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
