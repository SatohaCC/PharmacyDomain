"""Command結果とQuery結果を、既存の公開HTTP応答へ明示変換する。"""

from __future__ import annotations

from app.application.care_event.commands.dtos.create_event import (
    EventDto as Command_care_event_create_event_EventDto,
)
from app.application.care_event.commands.dtos.event_definition import (
    EventDefinitionDto as Command_care_event_event_definition_EventDefinitionDto,
)
from app.application.care_event.queries.dtos.create_event import (
    EventDto as Query_care_event_create_event_EventDto,
)
from app.application.care_event.queries.dtos.event_definition import (
    EventDefinitionDto as Query_care_event_event_definition_EventDefinitionDto,
)
from app.application.coverage.commands.dtos.get_coverage_selection import (
    CoverageSelectionDto as Command_coverage_get_coverage_selection_CoverageSelectionDto,
)
from app.application.coverage.commands.dtos.get_coverage_selection import (
    CoverageSelectionRecordDto as Command_coverage_get_coverage_selection_CoverageSelectionRecordDto,
)
from app.application.coverage.commands.dtos.get_coverage_selection import (
    InsuranceCoverageSelectionDto as Command_coverage_get_coverage_selection_InsuranceCoverageSelectionDto,
)
from app.application.coverage.commands.dtos.get_coverage_selection import (
    PublicExpenseCoverageSelectionDto as Command_coverage_get_coverage_selection_PublicExpenseCoverageSelectionDto,
)
from app.application.coverage.commands.dtos.get_patient_coverage import (
    PatientCoverageDto as Command_coverage_get_patient_coverage_PatientCoverageDto,
)
from app.application.coverage.queries.dtos.get_coverage_selection import (
    CoverageSelectionDto as Query_coverage_get_coverage_selection_CoverageSelectionDto,
)
from app.application.coverage.queries.dtos.get_coverage_selection import (
    CoverageSelectionRecordDto as Query_coverage_get_coverage_selection_CoverageSelectionRecordDto,
)
from app.application.coverage.queries.dtos.get_coverage_selection import (
    InsuranceCoverageSelectionDto as Query_coverage_get_coverage_selection_InsuranceCoverageSelectionDto,
)
from app.application.coverage.queries.dtos.get_coverage_selection import (
    PublicExpenseCoverageSelectionDto as Query_coverage_get_coverage_selection_PublicExpenseCoverageSelectionDto,
)
from app.application.coverage.queries.dtos.get_patient_coverage import (
    PatientCoverageDto as Query_coverage_get_patient_coverage_PatientCoverageDto,
)
from app.application.dispensing.commands.dtos.get_dispensing import (
    DispensedMedicineDto as Command_dispensing_get_dispensing_DispensedMedicineDto,
)
from app.application.dispensing.commands.dtos.get_dispensing import (
    DispensedRpDto as Command_dispensing_get_dispensing_DispensedRpDto,
)
from app.application.dispensing.commands.dtos.get_dispensing import (
    DispensingAuditDto as Command_dispensing_get_dispensing_DispensingAuditDto,
)
from app.application.dispensing.commands.dtos.get_dispensing import (
    DispensingProcessDto as Command_dispensing_get_dispensing_DispensingProcessDto,
)
from app.application.dispensing.commands.dtos.get_dispensing import (
    DispensingVerificationDto as Command_dispensing_get_dispensing_DispensingVerificationDto,
)
from app.application.dispensing.commands.dtos.get_dispensing import (
    DosageInstructionDto as Command_dispensing_get_dispensing_DosageInstructionDto,
)
from app.application.dispensing.commands.dtos.get_dispensing import (
    QuantityAdjustmentDto as Command_dispensing_get_dispensing_QuantityAdjustmentDto,
)
from app.application.dispensing.commands.dtos.get_dispensing import (
    SubstitutionDto as Command_dispensing_get_dispensing_SubstitutionDto,
)
from app.application.dispensing.queries.dtos.get_dispensing import (
    DispensedMedicineDto as Query_dispensing_get_dispensing_DispensedMedicineDto,
)
from app.application.dispensing.queries.dtos.get_dispensing import (
    DispensedRpDto as Query_dispensing_get_dispensing_DispensedRpDto,
)
from app.application.dispensing.queries.dtos.get_dispensing import (
    DispensingAuditDto as Query_dispensing_get_dispensing_DispensingAuditDto,
)
from app.application.dispensing.queries.dtos.get_dispensing import (
    DispensingProcessDto as Query_dispensing_get_dispensing_DispensingProcessDto,
)
from app.application.dispensing.queries.dtos.get_dispensing import (
    DispensingVerificationDto as Query_dispensing_get_dispensing_DispensingVerificationDto,
)
from app.application.dispensing.queries.dtos.get_dispensing import (
    DosageInstructionDto as Query_dispensing_get_dispensing_DosageInstructionDto,
)
from app.application.dispensing.queries.dtos.get_dispensing import (
    QuantityAdjustmentDto as Query_dispensing_get_dispensing_QuantityAdjustmentDto,
)
from app.application.dispensing.queries.dtos.get_dispensing import (
    SubstitutionDto as Query_dispensing_get_dispensing_SubstitutionDto,
)
from app.application.medication_history.commands.dtos.get_medication_history import (
    AmendmentDto as Command_medication_history_get_medication_history_AmendmentDto,
)
from app.application.medication_history.commands.dtos.get_medication_history import (
    BillingAdditionDto as Command_medication_history_get_medication_history_BillingAdditionDto,
)
from app.application.medication_history.commands.dtos.get_medication_history import (
    CategorizedNoteDto as Command_medication_history_get_medication_history_CategorizedNoteDto,
)
from app.application.medication_history.commands.dtos.get_medication_history import (
    ExternalCorrectionReviewEventDto as Command_medication_history_get_medication_history_ExternalCorrectionReviewEventDto,
)
from app.application.medication_history.commands.dtos.get_medication_history import (
    ExternalPrescriptionCorrectionDto as Command_medication_history_get_medication_history_ExternalPrescriptionCorrectionDto,
)
from app.application.medication_history.commands.dtos.get_medication_history import (
    HandbookStatusDto as Command_medication_history_get_medication_history_HandbookStatusDto,
)
from app.application.medication_history.commands.dtos.get_medication_history import (
    LabeledNoteDto as Command_medication_history_get_medication_history_LabeledNoteDto,
)
from app.application.medication_history.commands.dtos.get_medication_history import (
    MedicationHistoryDto as Command_medication_history_get_medication_history_MedicationHistoryDto,
)
from app.application.medication_history.commands.dtos.get_medication_history import (
    ResidualDrugDto as Command_medication_history_get_medication_history_ResidualDrugDto,
)
from app.application.medication_history.commands.dtos.get_medication_history import (
    SoapDto as Command_medication_history_get_medication_history_SoapDto,
)
from app.application.medication_history.commands.dtos.get_medication_history import (
    TracingReportDto as Command_medication_history_get_medication_history_TracingReportDto,
)
from app.application.medication_history.commands.dtos.get_medication_history import (
    TracingReportResponseDto as Command_medication_history_get_medication_history_TracingReportResponseDto,
)
from app.application.medication_history.commands.dtos.get_patient_medical_profile import (
    AdverseReactionDto as Command_medication_history_get_patient_medical_profile_AdverseReactionDto,
)
from app.application.medication_history.commands.dtos.get_patient_medical_profile import (
    AllergyDto as Command_medication_history_get_patient_medical_profile_AllergyDto,
)
from app.application.medication_history.commands.dtos.get_patient_medical_profile import (
    ConcurrentMedicationDto as Command_medication_history_get_patient_medical_profile_ConcurrentMedicationDto,
)
from app.application.medication_history.commands.dtos.get_patient_medical_profile import (
    FamilyPharmacistDto as Command_medication_history_get_patient_medical_profile_FamilyPharmacistDto,
)
from app.application.medication_history.commands.dtos.get_patient_medical_profile import (
    GenericPreferenceDto as Command_medication_history_get_patient_medical_profile_GenericPreferenceDto,
)
from app.application.medication_history.commands.dtos.get_patient_medical_profile import (
    LifestyleDto as Command_medication_history_get_patient_medical_profile_LifestyleDto,
)
from app.application.medication_history.commands.dtos.get_patient_medical_profile import (
    MedicalConditionDto as Command_medication_history_get_patient_medical_profile_MedicalConditionDto,
)
from app.application.medication_history.commands.dtos.get_patient_medical_profile import (
    PatientMedicalProfileDto as Command_medication_history_get_patient_medical_profile_PatientMedicalProfileDto,
)
from app.application.medication_history.commands.dtos.get_patient_medical_profile import (
    ProvenanceDto as Command_medication_history_get_patient_medical_profile_ProvenanceDto,
)
from app.application.medication_history.queries.dtos.get_medication_history import (
    AmendmentDto as Query_medication_history_get_medication_history_AmendmentDto,
)
from app.application.medication_history.queries.dtos.get_medication_history import (
    BillingAdditionDto as Query_medication_history_get_medication_history_BillingAdditionDto,
)
from app.application.medication_history.queries.dtos.get_medication_history import (
    CategorizedNoteDto as Query_medication_history_get_medication_history_CategorizedNoteDto,
)
from app.application.medication_history.queries.dtos.get_medication_history import (
    ExternalCorrectionReviewEventDto as Query_medication_history_get_medication_history_ExternalCorrectionReviewEventDto,
)
from app.application.medication_history.queries.dtos.get_medication_history import (
    ExternalPrescriptionCorrectionDto as Query_medication_history_get_medication_history_ExternalPrescriptionCorrectionDto,
)
from app.application.medication_history.queries.dtos.get_medication_history import (
    HandbookStatusDto as Query_medication_history_get_medication_history_HandbookStatusDto,
)
from app.application.medication_history.queries.dtos.get_medication_history import (
    LabeledNoteDto as Query_medication_history_get_medication_history_LabeledNoteDto,
)
from app.application.medication_history.queries.dtos.get_medication_history import (
    MedicationHistoryDto as Query_medication_history_get_medication_history_MedicationHistoryDto,
)
from app.application.medication_history.queries.dtos.get_medication_history import (
    ResidualDrugDto as Query_medication_history_get_medication_history_ResidualDrugDto,
)
from app.application.medication_history.queries.dtos.get_medication_history import (
    SoapDto as Query_medication_history_get_medication_history_SoapDto,
)
from app.application.medication_history.queries.dtos.get_medication_history import (
    TracingReportDto as Query_medication_history_get_medication_history_TracingReportDto,
)
from app.application.medication_history.queries.dtos.get_medication_history import (
    TracingReportResponseDto as Query_medication_history_get_medication_history_TracingReportResponseDto,
)
from app.application.medication_history.queries.dtos.get_patient_medical_profile import (
    AdverseReactionDto as Query_medication_history_get_patient_medical_profile_AdverseReactionDto,
)
from app.application.medication_history.queries.dtos.get_patient_medical_profile import (
    AllergyDto as Query_medication_history_get_patient_medical_profile_AllergyDto,
)
from app.application.medication_history.queries.dtos.get_patient_medical_profile import (
    ConcurrentMedicationDto as Query_medication_history_get_patient_medical_profile_ConcurrentMedicationDto,
)
from app.application.medication_history.queries.dtos.get_patient_medical_profile import (
    FamilyPharmacistDto as Query_medication_history_get_patient_medical_profile_FamilyPharmacistDto,
)
from app.application.medication_history.queries.dtos.get_patient_medical_profile import (
    GenericPreferenceDto as Query_medication_history_get_patient_medical_profile_GenericPreferenceDto,
)
from app.application.medication_history.queries.dtos.get_patient_medical_profile import (
    LifestyleDto as Query_medication_history_get_patient_medical_profile_LifestyleDto,
)
from app.application.medication_history.queries.dtos.get_patient_medical_profile import (
    MedicalConditionDto as Query_medication_history_get_patient_medical_profile_MedicalConditionDto,
)
from app.application.medication_history.queries.dtos.get_patient_medical_profile import (
    PatientMedicalProfileDto as Query_medication_history_get_patient_medical_profile_PatientMedicalProfileDto,
)
from app.application.medication_history.queries.dtos.get_patient_medical_profile import (
    ProvenanceDto as Query_medication_history_get_patient_medical_profile_ProvenanceDto,
)
from app.application.medicine_catalog.commands.dtos.get_medicine import (
    MedicineDto as Command_medicine_catalog_get_medicine_MedicineDto,
)
from app.application.medicine_catalog.queries.dtos.get_medicine import (
    MedicineDto as Query_medicine_catalog_get_medicine_MedicineDto,
)
from app.application.patient.commands.dtos.get_patient_heading import (
    PatientHeadingDto as Command_patient_get_patient_heading_PatientHeadingDto,
)
from app.application.patient.commands.dtos.get_patient_heading import (
    PatientHeadingRevisionDto as Command_patient_get_patient_heading_PatientHeadingRevisionDto,
)
from app.application.patient.commands.dtos.register_patient_external_identifier import (
    PatientExternalIdentifierDto as Command_patient_register_patient_external_identifier_PatientExternalIdentifierDto,
)
from app.application.patient.queries.dtos.get_patient_heading import (
    PatientHeadingDto as Query_patient_get_patient_heading_PatientHeadingDto,
)
from app.application.patient.queries.dtos.get_patient_heading import (
    PatientHeadingRevisionDto as Query_patient_get_patient_heading_PatientHeadingRevisionDto,
)
from app.application.patient.queries.dtos.register_patient_external_identifier import (
    PatientExternalIdentifierDto as Query_patient_register_patient_external_identifier_PatientExternalIdentifierDto,
)
from app.application.prescription.commands.dtos.get_prescription import (
    DepartmentDto as Command_prescription_get_prescription_DepartmentDto,
)
from app.application.prescription.commands.dtos.get_prescription import (
    DosageInstructionDto as Command_prescription_get_prescription_DosageInstructionDto,
)
from app.application.prescription.commands.dtos.get_prescription import (
    DosageSupplementDto as Command_prescription_get_prescription_DosageSupplementDto,
)
from app.application.prescription.commands.dtos.get_prescription import (
    MedicalInstitutionDto as Command_prescription_get_prescription_MedicalInstitutionDto,
)
from app.application.prescription.commands.dtos.get_prescription import (
    MedicineSupplementDto as Command_prescription_get_prescription_MedicineSupplementDto,
)
from app.application.prescription.commands.dtos.get_prescription import (
    PrescriberDto as Command_prescription_get_prescription_PrescriberDto,
)
from app.application.prescription.commands.dtos.get_prescription import (
    PrescriberResponseDto as Command_prescription_get_prescription_PrescriberResponseDto,
)
from app.application.prescription.commands.dtos.get_prescription import (
    PrescriptionDto as Command_prescription_get_prescription_PrescriptionDto,
)
from app.application.prescription.commands.dtos.get_prescription import (
    PrescriptionInquiryDto as Command_prescription_get_prescription_PrescriptionInquiryDto,
)
from app.application.prescription.commands.dtos.get_prescription import (
    PrescriptionManagementInfoDto as Command_prescription_get_prescription_PrescriptionManagementInfoDto,
)
from app.application.prescription.commands.dtos.get_prescription import (
    PrescriptionMedicineDto as Command_prescription_get_prescription_PrescriptionMedicineDto,
)
from app.application.prescription.commands.dtos.get_prescription import (
    PrescriptionPeriodDto as Command_prescription_get_prescription_PrescriptionPeriodDto,
)
from app.application.prescription.commands.dtos.get_prescription import (
    PrescriptionRpDto as Command_prescription_get_prescription_PrescriptionRpDto,
)
from app.application.prescription.commands.dtos.get_prescription import (
    PublicExpenseBurdenDto as Command_prescription_get_prescription_PublicExpenseBurdenDto,
)
from app.application.prescription.commands.dtos.get_prescription import (
    SubstitutionRestrictionDto as Command_prescription_get_prescription_SubstitutionRestrictionDto,
)
from app.application.prescription.commands.dtos.get_prescription import (
    UnitConversionDto as Command_prescription_get_prescription_UnitConversionDto,
)
from app.application.prescription.queries.dtos.get_prescription import (
    DepartmentDto as Query_prescription_get_prescription_DepartmentDto,
)
from app.application.prescription.queries.dtos.get_prescription import (
    DosageInstructionDto as Query_prescription_get_prescription_DosageInstructionDto,
)
from app.application.prescription.queries.dtos.get_prescription import (
    DosageSupplementDto as Query_prescription_get_prescription_DosageSupplementDto,
)
from app.application.prescription.queries.dtos.get_prescription import (
    MedicalInstitutionDto as Query_prescription_get_prescription_MedicalInstitutionDto,
)
from app.application.prescription.queries.dtos.get_prescription import (
    MedicineSupplementDto as Query_prescription_get_prescription_MedicineSupplementDto,
)
from app.application.prescription.queries.dtos.get_prescription import (
    PrescriberDto as Query_prescription_get_prescription_PrescriberDto,
)
from app.application.prescription.queries.dtos.get_prescription import (
    PrescriberResponseDto as Query_prescription_get_prescription_PrescriberResponseDto,
)
from app.application.prescription.queries.dtos.get_prescription import (
    PrescriptionDto as Query_prescription_get_prescription_PrescriptionDto,
)
from app.application.prescription.queries.dtos.get_prescription import (
    PrescriptionInquiryDto as Query_prescription_get_prescription_PrescriptionInquiryDto,
)
from app.application.prescription.queries.dtos.get_prescription import (
    PrescriptionManagementInfoDto as Query_prescription_get_prescription_PrescriptionManagementInfoDto,
)
from app.application.prescription.queries.dtos.get_prescription import (
    PrescriptionMedicineDto as Query_prescription_get_prescription_PrescriptionMedicineDto,
)
from app.application.prescription.queries.dtos.get_prescription import (
    PrescriptionPeriodDto as Query_prescription_get_prescription_PrescriptionPeriodDto,
)
from app.application.prescription.queries.dtos.get_prescription import (
    PrescriptionRpDto as Query_prescription_get_prescription_PrescriptionRpDto,
)
from app.application.prescription.queries.dtos.get_prescription import (
    PublicExpenseBurdenDto as Query_prescription_get_prescription_PublicExpenseBurdenDto,
)
from app.application.prescription.queries.dtos.get_prescription import (
    SubstitutionRestrictionDto as Query_prescription_get_prescription_SubstitutionRestrictionDto,
)
from app.application.prescription.queries.dtos.get_prescription import (
    UnitConversionDto as Query_prescription_get_prescription_UnitConversionDto,
)
from app.application.store.commands.dtos.business_hours import (
    BusinessDayExceptionDto as Command_store_business_hours_BusinessDayExceptionDto,
)
from app.application.store.commands.dtos.business_hours import (
    BusinessHoursDto as Command_store_business_hours_BusinessHoursDto,
)
from app.application.store.commands.dtos.business_hours import (
    BusinessHourSlotDto as Command_store_business_hours_BusinessHourSlotDto,
)
from app.application.store.commands.dtos.business_hours import (
    WeekdayBusinessHoursDto as Command_store_business_hours_WeekdayBusinessHoursDto,
)
from app.application.store.commands.dtos.get_store import (
    StoreDto as Command_store_get_store_StoreDto,
)
from app.application.store.commands.dtos.get_store import (
    StoreStatusChangeDto as Command_store_get_store_StoreStatusChangeDto,
)
from app.application.store.queries.dtos.business_hours import (
    BusinessDayExceptionDto as Query_store_business_hours_BusinessDayExceptionDto,
)
from app.application.store.queries.dtos.business_hours import (
    BusinessHoursDto as Query_store_business_hours_BusinessHoursDto,
)
from app.application.store.queries.dtos.business_hours import (
    BusinessHourSlotDto as Query_store_business_hours_BusinessHourSlotDto,
)
from app.application.store.queries.dtos.business_hours import (
    WeekdayBusinessHoursDto as Query_store_business_hours_WeekdayBusinessHoursDto,
)
from app.application.store.queries.dtos.get_store import (
    StoreDto as Query_store_get_store_StoreDto,
)
from app.application.store.queries.dtos.get_store import (
    StoreStatusChangeDto as Query_store_get_store_StoreStatusChangeDto,
)


def to_http_care_event_event_definition__event_definition_dto(
    value: Command_care_event_event_definition_EventDefinitionDto
    | Query_care_event_event_definition_EventDefinitionDto,
) -> Command_care_event_event_definition_EventDefinitionDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(value, Command_care_event_event_definition_EventDefinitionDto):
        return value
    return Command_care_event_event_definition_EventDefinitionDto(
        id=value.id,
        corporate_id=value.corporate_id,
        name=value.name,
        standard_code=value.standard_code,
        is_active=value.is_active,
    )


def to_http_care_event_create_event__event_dto(
    value: Command_care_event_create_event_EventDto
    | Query_care_event_create_event_EventDto,
) -> Command_care_event_create_event_EventDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(value, Command_care_event_create_event_EventDto):
        return value
    return Command_care_event_create_event_EventDto(
        event_id=value.event_id,
        medication_history_id=value.medication_history_id,
        event_type_id=value.event_type_id,
        event_type_name=value.event_type_name,
        corporate_id=value.corporate_id,
        store_id=value.store_id,
        patient_id=value.patient_id,
        occurred_at=value.occurred_at,
        occurred_at_is_unknown=value.occurred_at_is_unknown,
        created_at=value.created_at,
        related_event_id=value.related_event_id,
        reception_id=value.reception_id,
        prescription_id=value.prescription_id,
        dispensing_id=value.dispensing_id,
    )


def to_http_coverage_get_patient_coverage__patient_coverage_dto(
    value: Command_coverage_get_patient_coverage_PatientCoverageDto
    | Query_coverage_get_patient_coverage_PatientCoverageDto,
) -> Command_coverage_get_patient_coverage_PatientCoverageDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(value, Command_coverage_get_patient_coverage_PatientCoverageDto):
        return value
    return Command_coverage_get_patient_coverage_PatientCoverageDto(
        id=value.id,
        corporate_id=value.corporate_id,
        patient_id=value.patient_id,
        coverage_type=value.coverage_type,
        valid_from=value.valid_from,
        valid_to=value.valid_to,
        activated_on=value.activated_on,
        deactivated_on=value.deactivated_on,
        priority=value.priority,
        insurer_number=value.insurer_number,
        insured_symbol=value.insured_symbol,
        insured_number=value.insured_number,
        branch_number=value.branch_number,
        insured_type=value.insured_type,
        benefit_ratio=value.benefit_ratio,
        payer_number=value.payer_number,
        recipient_number=value.recipient_number,
    )


def to_http_dispensing_get_dispensing__dispensing_process_dto(
    value: Command_dispensing_get_dispensing_DispensingProcessDto
    | Query_dispensing_get_dispensing_DispensingProcessDto,
) -> Command_dispensing_get_dispensing_DispensingProcessDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(value, Command_dispensing_get_dispensing_DispensingProcessDto):
        return value
    return Command_dispensing_get_dispensing_DispensingProcessDto(
        id=value.id,
        corporate_id=value.corporate_id,
        store_id=value.store_id,
        patient_id=value.patient_id,
        prescription_id=value.prescription_id,
        iteration=value.iteration,
        dispensed_date=value.dispensed_date,
        dispenser_id=value.dispenser_id,
        started_at=value.started_at,
        status=value.status,
        completion_type=value.completion_type,
        split_reason=value.split_reason,
        total_split_count=value.total_split_count,
        next_dispensing_date=value.next_dispensing_date,
        dispensed_rps=tuple(
            to_http_dispensing_get_dispensing__dispensed_rp_dto(item)
            for item in value.dispensed_rps
        ),
        audit=to_http_dispensing_get_dispensing__dispensing_audit_dto(value.audit)
        if value.audit is not None
        else None,
        verification=to_http_dispensing_get_dispensing__dispensing_verification_dto(
            value.verification
        )
        if value.verification is not None
        else None,
        cancellation_reason=value.cancellation_reason,
    )


def to_http_dispensing_get_dispensing__dispensed_rp_dto(
    value: Command_dispensing_get_dispensing_DispensedRpDto
    | Query_dispensing_get_dispensing_DispensedRpDto,
) -> Command_dispensing_get_dispensing_DispensedRpDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(value, Command_dispensing_get_dispensing_DispensedRpDto):
        return value
    return Command_dispensing_get_dispensing_DispensedRpDto(
        rp_number=value.rp_number,
        category=value.category,
        quantity=value.quantity,
        dosage_instruction=to_http_dispensing_get_dispensing__dosage_instruction_dto(
            value.dosage_instruction
        ),
        medicines=tuple(
            to_http_dispensing_get_dispensing__dispensed_medicine_dto(item)
            for item in value.medicines
        ),
        quantity_adjustment=to_http_dispensing_get_dispensing__quantity_adjustment_dto(
            value.quantity_adjustment
        )
        if value.quantity_adjustment is not None
        else None,
    )


def to_http_dispensing_get_dispensing__dosage_instruction_dto(
    value: Command_dispensing_get_dispensing_DosageInstructionDto
    | Query_dispensing_get_dispensing_DosageInstructionDto,
) -> Command_dispensing_get_dispensing_DosageInstructionDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(value, Command_dispensing_get_dispensing_DosageInstructionDto):
        return value
    return Command_dispensing_get_dispensing_DosageInstructionDto(
        code_type=value.code_type,
        name=value.name,
        code=value.code,
        daily_frequency=value.daily_frequency,
    )


def to_http_dispensing_get_dispensing__dispensed_medicine_dto(
    value: Command_dispensing_get_dispensing_DispensedMedicineDto
    | Query_dispensing_get_dispensing_DispensedMedicineDto,
) -> Command_dispensing_get_dispensing_DispensedMedicineDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(value, Command_dispensing_get_dispensing_DispensedMedicineDto):
        return value
    return Command_dispensing_get_dispensing_DispensedMedicineDto(
        line_number=value.line_number,
        code_type=value.code_type,
        code=value.code,
        name=value.name,
        amount=value.amount,
        unit=value.unit,
        substitution=to_http_dispensing_get_dispensing__substitution_dto(
            value.substitution
        )
        if value.substitution is not None
        else None,
        preparations=value.preparations,
        public_expense_first=value.public_expense_first,
        public_expense_second=value.public_expense_second,
        public_expense_third=value.public_expense_third,
        public_expense_special=value.public_expense_special,
    )


def to_http_dispensing_get_dispensing__substitution_dto(
    value: Command_dispensing_get_dispensing_SubstitutionDto
    | Query_dispensing_get_dispensing_SubstitutionDto,
) -> Command_dispensing_get_dispensing_SubstitutionDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(value, Command_dispensing_get_dispensing_SubstitutionDto):
        return value
    return Command_dispensing_get_dispensing_SubstitutionDto(
        category=value.category,
        original_code_type=value.original_code_type,
        original_code=value.original_code,
        original_name=value.original_name,
        reason=value.reason,
        inquiry_number=value.inquiry_number,
    )


def to_http_dispensing_get_dispensing__quantity_adjustment_dto(
    value: Command_dispensing_get_dispensing_QuantityAdjustmentDto
    | Query_dispensing_get_dispensing_QuantityAdjustmentDto,
) -> Command_dispensing_get_dispensing_QuantityAdjustmentDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(value, Command_dispensing_get_dispensing_QuantityAdjustmentDto):
        return value
    return Command_dispensing_get_dispensing_QuantityAdjustmentDto(
        prescribed_quantity=value.prescribed_quantity,
        reason=value.reason,
        inquiry_number=value.inquiry_number,
    )


def to_http_dispensing_get_dispensing__dispensing_audit_dto(
    value: Command_dispensing_get_dispensing_DispensingAuditDto
    | Query_dispensing_get_dispensing_DispensingAuditDto,
) -> Command_dispensing_get_dispensing_DispensingAuditDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(value, Command_dispensing_get_dispensing_DispensingAuditDto):
        return value
    return Command_dispensing_get_dispensing_DispensingAuditDto(
        auditor_id=value.auditor_id,
        audited_at=value.audited_at,
        has_issues=value.has_issues,
        notes=value.notes,
    )


def to_http_dispensing_get_dispensing__dispensing_verification_dto(
    value: Command_dispensing_get_dispensing_DispensingVerificationDto
    | Query_dispensing_get_dispensing_DispensingVerificationDto,
) -> Command_dispensing_get_dispensing_DispensingVerificationDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(value, Command_dispensing_get_dispensing_DispensingVerificationDto):
        return value
    return Command_dispensing_get_dispensing_DispensingVerificationDto(
        verifier_id=value.verifier_id,
        verified_at=value.verified_at,
        result=value.result,
        notes=value.notes,
    )


def to_http_medication_history_get_medication_history__medication_history_dto(
    value: Command_medication_history_get_medication_history_MedicationHistoryDto
    | Query_medication_history_get_medication_history_MedicationHistoryDto,
) -> Command_medication_history_get_medication_history_MedicationHistoryDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(
        value, Command_medication_history_get_medication_history_MedicationHistoryDto
    ):
        return value
    return Command_medication_history_get_medication_history_MedicationHistoryDto(
        id=value.id,
        corporate_id=value.corporate_id,
        store_id=value.store_id,
        patient_id=value.patient_id,
        event_id=value.event_id,
        event_type_id=value.event_type_id,
        event_type_name=value.event_type_name,
        event_occurred_at=value.event_occurred_at,
        event_occurred_at_is_unknown=value.event_occurred_at_is_unknown,
        dispensing_id=value.dispensing_id,
        prescription_id=value.prescription_id,
        counselor_id=value.counselor_id,
        counseled_at=value.counseled_at,
        method=value.method,
        status=value.status,
        soap=to_http_medication_history_get_medication_history__soap_dto(value.soap),
        effective_soap=to_http_medication_history_get_medication_history__soap_dto(
            value.effective_soap
        ),
        handbook_status=to_http_medication_history_get_medication_history__handbook_status_dto(
            value.handbook_status
        )
        if value.handbook_status is not None
        else None,
        residual_drug=to_http_medication_history_get_medication_history__residual_drug_dto(
            value.residual_drug
        )
        if value.residual_drug is not None
        else None,
        information_sheet_provided=value.information_sheet_provided,
        source_system=value.source_system,
        imported_at=value.imported_at,
        amendments=tuple(
            to_http_medication_history_get_medication_history__amendment_dto(item)
            for item in value.amendments
        ),
        external_corrections=tuple(
            to_http_medication_history_get_medication_history__external_prescription_correction_dto(
                item
            )
            for item in value.external_corrections
        ),
        updates_profile=value.updates_profile,
        profile_updates=value.profile_updates,
        original_facts=value.original_facts,
        fact_corrections=value.fact_corrections,
        additional_notes=tuple(
            to_http_medication_history_get_medication_history__categorized_note_dto(
                item
            )
            for item in value.additional_notes
        ),
        billing_additions=tuple(
            to_http_medication_history_get_medication_history__billing_addition_dto(
                item
            )
            for item in value.billing_additions
        ),
        tracing_reports=tuple(
            to_http_medication_history_get_medication_history__tracing_report_dto(item)
            for item in value.tracing_reports
        ),
        finalized_at=value.finalized_at,
        finalized_by=value.finalized_by,
        delay_reason=value.delay_reason,
        recorded_by=value.recorded_by,
        review_result=value.review_result,
        recorded_at=value.recorded_at,
    )


def to_http_medication_history_get_medication_history__soap_dto(
    value: Command_medication_history_get_medication_history_SoapDto
    | Query_medication_history_get_medication_history_SoapDto,
) -> Command_medication_history_get_medication_history_SoapDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(value, Command_medication_history_get_medication_history_SoapDto):
        return value
    return Command_medication_history_get_medication_history_SoapDto(
        subjective=tuple(
            to_http_medication_history_get_medication_history__labeled_note_dto(item)
            for item in value.subjective
        ),
        objective=tuple(
            to_http_medication_history_get_medication_history__labeled_note_dto(item)
            for item in value.objective
        ),
        assessment=tuple(
            to_http_medication_history_get_medication_history__labeled_note_dto(item)
            for item in value.assessment
        ),
        plan=tuple(
            to_http_medication_history_get_medication_history__labeled_note_dto(item)
            for item in value.plan
        ),
    )


def to_http_medication_history_get_medication_history__labeled_note_dto(
    value: Command_medication_history_get_medication_history_LabeledNoteDto
    | Query_medication_history_get_medication_history_LabeledNoteDto,
) -> Command_medication_history_get_medication_history_LabeledNoteDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(
        value, Command_medication_history_get_medication_history_LabeledNoteDto
    ):
        return value
    return Command_medication_history_get_medication_history_LabeledNoteDto(
        category=value.category, category_label=value.category_label, text=value.text
    )


def to_http_medication_history_get_medication_history__handbook_status_dto(
    value: Command_medication_history_get_medication_history_HandbookStatusDto
    | Query_medication_history_get_medication_history_HandbookStatusDto,
) -> Command_medication_history_get_medication_history_HandbookStatusDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(
        value, Command_medication_history_get_medication_history_HandbookStatusDto
    ):
        return value
    return Command_medication_history_get_medication_history_HandbookStatusDto(
        presented=value.presented,
        not_presented_reason=value.not_presented_reason,
        guidance_provided=value.guidance_provided,
        multiple_handbooks_not_consolidated_reason=value.multiple_handbooks_not_consolidated_reason,
    )


def to_http_medication_history_get_medication_history__residual_drug_dto(
    value: Command_medication_history_get_medication_history_ResidualDrugDto
    | Query_medication_history_get_medication_history_ResidualDrugDto,
) -> Command_medication_history_get_medication_history_ResidualDrugDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(
        value, Command_medication_history_get_medication_history_ResidualDrugDto
    ):
        return value
    return Command_medication_history_get_medication_history_ResidualDrugDto(
        has_residual_drugs=value.has_residual_drugs,
        quantity=value.quantity,
        reason=value.reason,
    )


def to_http_medication_history_get_medication_history__amendment_dto(
    value: Command_medication_history_get_medication_history_AmendmentDto
    | Query_medication_history_get_medication_history_AmendmentDto,
) -> Command_medication_history_get_medication_history_AmendmentDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(
        value, Command_medication_history_get_medication_history_AmendmentDto
    ):
        return value
    return Command_medication_history_get_medication_history_AmendmentDto(
        amended_soap=to_http_medication_history_get_medication_history__soap_dto(
            value.amended_soap
        ),
        reason=value.reason,
        amended_by=value.amended_by,
        amended_at=value.amended_at,
        amendment_id=value.amendment_id,
    )


def to_http_medication_history_get_medication_history__external_prescription_correction_dto(
    value: Command_medication_history_get_medication_history_ExternalPrescriptionCorrectionDto
    | Query_medication_history_get_medication_history_ExternalPrescriptionCorrectionDto,
) -> (
    Command_medication_history_get_medication_history_ExternalPrescriptionCorrectionDto
):
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(
        value,
        Command_medication_history_get_medication_history_ExternalPrescriptionCorrectionDto,
    ):
        return value
    return Command_medication_history_get_medication_history_ExternalPrescriptionCorrectionDto(
        correction_id=value.correction_id,
        kind=value.kind,
        status=value.status,
        corrected_at=value.corrected_at,
        source_document_number=value.source_document_number,
        reason=value.reason,
        details=value.details,
        acknowledged_by=value.acknowledged_by,
        acknowledged_at=value.acknowledged_at,
        review_events=tuple(
            to_http_medication_history_get_medication_history__external_correction_review_event_dto(
                item
            )
            for item in value.review_events
        ),
    )


def to_http_medication_history_get_medication_history__external_correction_review_event_dto(
    value: Command_medication_history_get_medication_history_ExternalCorrectionReviewEventDto
    | Query_medication_history_get_medication_history_ExternalCorrectionReviewEventDto,
) -> Command_medication_history_get_medication_history_ExternalCorrectionReviewEventDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(
        value,
        Command_medication_history_get_medication_history_ExternalCorrectionReviewEventDto,
    ):
        return value
    return Command_medication_history_get_medication_history_ExternalCorrectionReviewEventDto(
        decision=value.decision,
        reason=value.reason,
        reviewed_by=value.reviewed_by,
        reviewed_at=value.reviewed_at,
        matched_prescription_id=value.matched_prescription_id,
        amendment_id=value.amendment_id,
    )


def to_http_medication_history_get_medication_history__categorized_note_dto(
    value: Command_medication_history_get_medication_history_CategorizedNoteDto
    | Query_medication_history_get_medication_history_CategorizedNoteDto,
) -> Command_medication_history_get_medication_history_CategorizedNoteDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(
        value, Command_medication_history_get_medication_history_CategorizedNoteDto
    ):
        return value
    return Command_medication_history_get_medication_history_CategorizedNoteDto(
        major_category_code=value.major_category_code,
        medium_category_code=value.medium_category_code,
        text=value.text,
        category=value.category,
        id=value.id,
    )


def to_http_medication_history_get_medication_history__billing_addition_dto(
    value: Command_medication_history_get_medication_history_BillingAdditionDto
    | Query_medication_history_get_medication_history_BillingAdditionDto,
) -> Command_medication_history_get_medication_history_BillingAdditionDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(
        value, Command_medication_history_get_medication_history_BillingAdditionDto
    ):
        return value
    return Command_medication_history_get_medication_history_BillingAdditionDto(
        code=value.code,
        name=value.name,
        points=value.points,
        quantity=value.quantity,
        id=value.id,
    )


def to_http_medication_history_get_medication_history__tracing_report_dto(
    value: Command_medication_history_get_medication_history_TracingReportDto
    | Query_medication_history_get_medication_history_TracingReportDto,
) -> Command_medication_history_get_medication_history_TracingReportDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(
        value, Command_medication_history_get_medication_history_TracingReportDto
    ):
        return value
    return Command_medication_history_get_medication_history_TracingReportDto(
        id=value.id,
        reporter_id=value.reporter_id,
        provided_at=value.provided_at,
        medical_institution_name=value.medical_institution_name,
        physician_name=value.physician_name,
        category=value.category,
        fee_category=value.fee_category,
        delivery_method=value.delivery_method,
        content=value.content,
        response=to_http_medication_history_get_medication_history__tracing_report_response_dto(
            value.response
        )
        if value.response is not None
        else None,
    )


def to_http_medication_history_get_medication_history__tracing_report_response_dto(
    value: Command_medication_history_get_medication_history_TracingReportResponseDto
    | Query_medication_history_get_medication_history_TracingReportResponseDto,
) -> Command_medication_history_get_medication_history_TracingReportResponseDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(
        value,
        Command_medication_history_get_medication_history_TracingReportResponseDto,
    ):
        return value
    return Command_medication_history_get_medication_history_TracingReportResponseDto(
        responded_at=value.responded_at,
        action_type=value.action_type,
        content=value.content,
        received_by=value.received_by,
        acknowledged_physician_name=value.acknowledged_physician_name,
    )


def to_http_medication_history_get_patient_medical_profile__patient_medical_profile_dto(
    value: Command_medication_history_get_patient_medical_profile_PatientMedicalProfileDto
    | Query_medication_history_get_patient_medical_profile_PatientMedicalProfileDto,
) -> Command_medication_history_get_patient_medical_profile_PatientMedicalProfileDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(
        value,
        Command_medication_history_get_patient_medical_profile_PatientMedicalProfileDto,
    ):
        return value
    return Command_medication_history_get_patient_medical_profile_PatientMedicalProfileDto(
        id=value.id,
        corporate_id=value.corporate_id,
        patient_id=value.patient_id,
        allergies=tuple(
            to_http_medication_history_get_patient_medical_profile__allergy_dto(item)
            for item in value.allergies
        ),
        adverse_reactions=tuple(
            to_http_medication_history_get_patient_medical_profile__adverse_reaction_dto(
                item
            )
            for item in value.adverse_reactions
        ),
        medical_conditions=tuple(
            to_http_medication_history_get_patient_medical_profile__medical_condition_dto(
                item
            )
            for item in value.medical_conditions
        ),
        concurrent_medications=tuple(
            to_http_medication_history_get_patient_medical_profile__concurrent_medication_dto(
                item
            )
            for item in value.concurrent_medications
        ),
        active_concurrent_medications=tuple(
            to_http_medication_history_get_patient_medical_profile__concurrent_medication_dto(
                item
            )
            for item in value.active_concurrent_medications
        ),
        lifestyle=to_http_medication_history_get_patient_medical_profile__lifestyle_dto(
            value.lifestyle
        )
        if value.lifestyle is not None
        else None,
        generic_preference=to_http_medication_history_get_patient_medical_profile__generic_preference_dto(
            value.generic_preference
        )
        if value.generic_preference is not None
        else None,
        family_pharmacist=to_http_medication_history_get_patient_medical_profile__family_pharmacist_dto(
            value.family_pharmacist
        )
        if value.family_pharmacist is not None
        else None,
    )


def to_http_medication_history_get_patient_medical_profile__allergy_dto(
    value: Command_medication_history_get_patient_medical_profile_AllergyDto
    | Query_medication_history_get_patient_medical_profile_AllergyDto,
) -> Command_medication_history_get_patient_medical_profile_AllergyDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(
        value, Command_medication_history_get_patient_medical_profile_AllergyDto
    ):
        return value
    return Command_medication_history_get_patient_medical_profile_AllergyDto(
        allergen=value.allergen,
        reaction=value.reaction,
        severity=value.severity,
        provenance=to_http_medication_history_get_patient_medical_profile__provenance_dto(
            value.provenance
        ),
    )


def to_http_medication_history_get_patient_medical_profile__provenance_dto(
    value: Command_medication_history_get_patient_medical_profile_ProvenanceDto
    | Query_medication_history_get_patient_medical_profile_ProvenanceDto,
) -> Command_medication_history_get_patient_medical_profile_ProvenanceDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(
        value, Command_medication_history_get_patient_medical_profile_ProvenanceDto
    ):
        return value
    return Command_medication_history_get_patient_medical_profile_ProvenanceDto(
        source_record_id=value.source_record_id,
        recorded_by=value.recorded_by,
        recorded_on=value.recorded_on,
    )


def to_http_medication_history_get_patient_medical_profile__adverse_reaction_dto(
    value: Command_medication_history_get_patient_medical_profile_AdverseReactionDto
    | Query_medication_history_get_patient_medical_profile_AdverseReactionDto,
) -> Command_medication_history_get_patient_medical_profile_AdverseReactionDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(
        value, Command_medication_history_get_patient_medical_profile_AdverseReactionDto
    ):
        return value
    return Command_medication_history_get_patient_medical_profile_AdverseReactionDto(
        medicine_name=value.medicine_name,
        symptom=value.symptom,
        occurred_on=value.occurred_on,
        provenance=to_http_medication_history_get_patient_medical_profile__provenance_dto(
            value.provenance
        ),
    )


def to_http_medication_history_get_patient_medical_profile__medical_condition_dto(
    value: Command_medication_history_get_patient_medical_profile_MedicalConditionDto
    | Query_medication_history_get_patient_medical_profile_MedicalConditionDto,
) -> Command_medication_history_get_patient_medical_profile_MedicalConditionDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(
        value,
        Command_medication_history_get_patient_medical_profile_MedicalConditionDto,
    ):
        return value
    return Command_medication_history_get_patient_medical_profile_MedicalConditionDto(
        condition_name=value.condition_name,
        condition_status=value.condition_status,
        is_contraindication_target=value.is_contraindication_target,
        provenance=to_http_medication_history_get_patient_medical_profile__provenance_dto(
            value.provenance
        ),
    )


def to_http_medication_history_get_patient_medical_profile__concurrent_medication_dto(
    value: Command_medication_history_get_patient_medical_profile_ConcurrentMedicationDto
    | Query_medication_history_get_patient_medical_profile_ConcurrentMedicationDto,
) -> Command_medication_history_get_patient_medical_profile_ConcurrentMedicationDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(
        value,
        Command_medication_history_get_patient_medical_profile_ConcurrentMedicationDto,
    ):
        return value
    return Command_medication_history_get_patient_medical_profile_ConcurrentMedicationDto(
        medicine_name=value.medicine_name,
        category=value.category,
        started_on=value.started_on,
        ended_on=value.ended_on,
        prescriber_institution=value.prescriber_institution,
        provenance=to_http_medication_history_get_patient_medical_profile__provenance_dto(
            value.provenance
        ),
    )


def to_http_medication_history_get_patient_medical_profile__lifestyle_dto(
    value: Command_medication_history_get_patient_medical_profile_LifestyleDto
    | Query_medication_history_get_patient_medical_profile_LifestyleDto,
) -> Command_medication_history_get_patient_medical_profile_LifestyleDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(
        value, Command_medication_history_get_patient_medical_profile_LifestyleDto
    ):
        return value
    return Command_medication_history_get_patient_medical_profile_LifestyleDto(
        note=value.note,
        provenance=to_http_medication_history_get_patient_medical_profile__provenance_dto(
            value.provenance
        ),
    )


def to_http_medication_history_get_patient_medical_profile__generic_preference_dto(
    value: Command_medication_history_get_patient_medical_profile_GenericPreferenceDto
    | Query_medication_history_get_patient_medical_profile_GenericPreferenceDto,
) -> Command_medication_history_get_patient_medical_profile_GenericPreferenceDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(
        value,
        Command_medication_history_get_patient_medical_profile_GenericPreferenceDto,
    ):
        return value
    return Command_medication_history_get_patient_medical_profile_GenericPreferenceDto(
        preference=value.preference,
        provenance=to_http_medication_history_get_patient_medical_profile__provenance_dto(
            value.provenance
        ),
    )


def to_http_medication_history_get_patient_medical_profile__family_pharmacist_dto(
    value: Command_medication_history_get_patient_medical_profile_FamilyPharmacistDto
    | Query_medication_history_get_patient_medical_profile_FamilyPharmacistDto,
) -> Command_medication_history_get_patient_medical_profile_FamilyPharmacistDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(
        value,
        Command_medication_history_get_patient_medical_profile_FamilyPharmacistDto,
    ):
        return value
    return Command_medication_history_get_patient_medical_profile_FamilyPharmacistDto(
        pharmacist_id=value.pharmacist_id,
        agreed_on=value.agreed_on,
        provenance=to_http_medication_history_get_patient_medical_profile__provenance_dto(
            value.provenance
        ),
    )


def to_http_medicine_catalog_get_medicine__medicine_dto(
    value: Command_medicine_catalog_get_medicine_MedicineDto
    | Query_medicine_catalog_get_medicine_MedicineDto,
) -> Command_medicine_catalog_get_medicine_MedicineDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(value, Command_medicine_catalog_get_medicine_MedicineDto):
        return value
    return Command_medicine_catalog_get_medicine_MedicineDto(
        id=value.id,
        code_type=value.code_type,
        code=value.code,
        name=value.name,
        unit=value.unit,
        dosage_form=value.dosage_form,
        listed_on=value.listed_on,
        withdrawn_on=value.withdrawn_on,
        catalog_version=value.catalog_version,
        narcotic_category=value.narcotic_category,
        generic_category=value.generic_category,
        has_dosage_limit=value.has_dosage_limit,
        is_analgesic_antiinflammatory=value.is_analgesic_antiinflammatory,
        is_dermatological=value.is_dermatological,
        is_narcotic=value.is_narcotic,
        is_refill_restricted_patch=value.is_refill_restricted_patch,
        forbids_refill=value.forbids_refill,
    )


def to_http_patient_get_patient_heading__patient_heading_dto(
    value: Command_patient_get_patient_heading_PatientHeadingDto
    | Query_patient_get_patient_heading_PatientHeadingDto,
) -> Command_patient_get_patient_heading_PatientHeadingDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(value, Command_patient_get_patient_heading_PatientHeadingDto):
        return value
    return Command_patient_get_patient_heading_PatientHeadingDto(
        patient_id=value.patient_id,
        revision=value.revision,
        summary=value.summary,
        notes=value.notes,
        updated_by_person_id=value.updated_by_person_id,
        updated_by_account_id=value.updated_by_account_id,
        updated_at=value.updated_at,
        history=tuple(
            to_http_patient_get_patient_heading__patient_heading_revision_dto(item)
            for item in value.history
        ),
    )


def to_http_patient_get_patient_heading__patient_heading_revision_dto(
    value: Command_patient_get_patient_heading_PatientHeadingRevisionDto
    | Query_patient_get_patient_heading_PatientHeadingRevisionDto,
) -> Command_patient_get_patient_heading_PatientHeadingRevisionDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(value, Command_patient_get_patient_heading_PatientHeadingRevisionDto):
        return value
    return Command_patient_get_patient_heading_PatientHeadingRevisionDto(
        revision=value.revision,
        summary=value.summary,
        notes=value.notes,
        person_id=value.person_id,
        account_id=value.account_id,
        recorded_at=value.recorded_at,
    )


def to_http_patient_register_patient_external_identifier__patient_external_identifier_dto(
    value: Command_patient_register_patient_external_identifier_PatientExternalIdentifierDto
    | Query_patient_register_patient_external_identifier_PatientExternalIdentifierDto,
) -> Command_patient_register_patient_external_identifier_PatientExternalIdentifierDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(
        value,
        Command_patient_register_patient_external_identifier_PatientExternalIdentifierDto,
    ):
        return value
    return Command_patient_register_patient_external_identifier_PatientExternalIdentifierDto(
        id=value.id,
        corporate_id=value.corporate_id,
        patient_id=value.patient_id,
        system_name=value.system_name,
        external_patient_id=value.external_patient_id,
        store_id=value.store_id,
        is_active=value.is_active,
    )


def to_http_prescription_get_prescription__prescription_dto(
    value: Command_prescription_get_prescription_PrescriptionDto
    | Query_prescription_get_prescription_PrescriptionDto,
) -> Command_prescription_get_prescription_PrescriptionDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(value, Command_prescription_get_prescription_PrescriptionDto):
        return value
    return Command_prescription_get_prescription_PrescriptionDto(
        id=value.id,
        corporate_id=value.corporate_id,
        store_id=value.store_id,
        patient_id=value.patient_id,
        source_type=value.source_type,
        document_number=value.document_number,
        status=value.status,
        medical_institution=to_http_prescription_get_prescription__medical_institution_dto(
            value.medical_institution
        ),
        department=to_http_prescription_get_prescription__department_dto(
            value.department
        ),
        prescriber=to_http_prescription_get_prescription__prescriber_dto(
            value.prescriber
        ),
        period=to_http_prescription_get_prescription__prescription_period_dto(
            value.period
        ),
        rps=tuple(
            to_http_prescription_get_prescription__prescription_rp_dto(item)
            for item in value.rps
        ),
        management_info=to_http_prescription_get_prescription__prescription_management_info_dto(
            value.management_info
        ),
        inquiries=tuple(
            to_http_prescription_get_prescription__prescription_inquiry_dto(item)
            for item in value.inquiries
        ),
        coverage_selection_record_id=value.coverage_selection_record_id,
        has_open_inquiry=value.has_open_inquiry,
    )


def to_http_prescription_get_prescription__medical_institution_dto(
    value: Command_prescription_get_prescription_MedicalInstitutionDto
    | Query_prescription_get_prescription_MedicalInstitutionDto,
) -> Command_prescription_get_prescription_MedicalInstitutionDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(value, Command_prescription_get_prescription_MedicalInstitutionDto):
        return value
    return Command_prescription_get_prescription_MedicalInstitutionDto(
        code_type=value.code_type,
        code=value.code,
        prefecture_code=value.prefecture_code,
        name=value.name,
        postal_code=value.postal_code,
        address=value.address,
        phone_number=value.phone_number,
        fax_number=value.fax_number,
    )


def to_http_prescription_get_prescription__department_dto(
    value: Command_prescription_get_prescription_DepartmentDto
    | Query_prescription_get_prescription_DepartmentDto,
) -> Command_prescription_get_prescription_DepartmentDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(value, Command_prescription_get_prescription_DepartmentDto):
        return value
    return Command_prescription_get_prescription_DepartmentDto(
        code_type=value.code_type, name=value.name, code=value.code
    )


def to_http_prescription_get_prescription__prescriber_dto(
    value: Command_prescription_get_prescription_PrescriberDto
    | Query_prescription_get_prescription_PrescriberDto,
) -> Command_prescription_get_prescription_PrescriberDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(value, Command_prescription_get_prescription_PrescriberDto):
        return value
    return Command_prescription_get_prescription_PrescriberDto(
        full_name=value.full_name, full_name_kana=value.full_name_kana, code=value.code
    )


def to_http_prescription_get_prescription__prescription_period_dto(
    value: Command_prescription_get_prescription_PrescriptionPeriodDto
    | Query_prescription_get_prescription_PrescriptionPeriodDto,
) -> Command_prescription_get_prescription_PrescriptionPeriodDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(value, Command_prescription_get_prescription_PrescriptionPeriodDto):
        return value
    return Command_prescription_get_prescription_PrescriptionPeriodDto(
        issued_date=value.issued_date, valid_to=value.valid_to
    )


def to_http_prescription_get_prescription__prescription_rp_dto(
    value: Command_prescription_get_prescription_PrescriptionRpDto
    | Query_prescription_get_prescription_PrescriptionRpDto,
) -> Command_prescription_get_prescription_PrescriptionRpDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(value, Command_prescription_get_prescription_PrescriptionRpDto):
        return value
    return Command_prescription_get_prescription_PrescriptionRpDto(
        rp_number=value.rp_number,
        category=value.category,
        quantity=value.quantity,
        dosage_instruction=to_http_prescription_get_prescription__dosage_instruction_dto(
            value.dosage_instruction
        ),
        medicines=tuple(
            to_http_prescription_get_prescription__prescription_medicine_dto(item)
            for item in value.medicines
        ),
        custom_category_name=value.custom_category_name,
        dosage_supplements=tuple(
            to_http_prescription_get_prescription__dosage_supplement_dto(item)
            for item in value.dosage_supplements
        ),
    )


def to_http_prescription_get_prescription__dosage_instruction_dto(
    value: Command_prescription_get_prescription_DosageInstructionDto
    | Query_prescription_get_prescription_DosageInstructionDto,
) -> Command_prescription_get_prescription_DosageInstructionDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(value, Command_prescription_get_prescription_DosageInstructionDto):
        return value
    return Command_prescription_get_prescription_DosageInstructionDto(
        code_type=value.code_type,
        name=value.name,
        code=value.code,
        daily_frequency=value.daily_frequency,
    )


def to_http_prescription_get_prescription__prescription_medicine_dto(
    value: Command_prescription_get_prescription_PrescriptionMedicineDto
    | Query_prescription_get_prescription_PrescriptionMedicineDto,
) -> Command_prescription_get_prescription_PrescriptionMedicineDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(value, Command_prescription_get_prescription_PrescriptionMedicineDto):
        return value
    return Command_prescription_get_prescription_PrescriptionMedicineDto(
        line_number=value.line_number,
        code_type=value.code_type,
        code=value.code,
        name=value.name,
        amount=value.amount,
        unit=value.unit,
        single_dose=value.single_dose,
        unequal_doses=value.unequal_doses,
        unit_conversion=to_http_prescription_get_prescription__unit_conversion_dto(
            value.unit_conversion
        )
        if value.unit_conversion is not None
        else None,
        substitution_restriction=to_http_prescription_get_prescription__substitution_restriction_dto(
            value.substitution_restriction
        )
        if value.substitution_restriction is not None
        else None,
        public_expense_burden=to_http_prescription_get_prescription__public_expense_burden_dto(
            value.public_expense_burden
        )
        if value.public_expense_burden is not None
        else None,
        supplements=tuple(
            to_http_prescription_get_prescription__medicine_supplement_dto(item)
            for item in value.supplements
        ),
    )


def to_http_prescription_get_prescription__unit_conversion_dto(
    value: Command_prescription_get_prescription_UnitConversionDto
    | Query_prescription_get_prescription_UnitConversionDto,
) -> Command_prescription_get_prescription_UnitConversionDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(value, Command_prescription_get_prescription_UnitConversionDto):
        return value
    return Command_prescription_get_prescription_UnitConversionDto(
        factor=value.factor, tariff_unit=value.tariff_unit
    )


def to_http_prescription_get_prescription__substitution_restriction_dto(
    value: Command_prescription_get_prescription_SubstitutionRestrictionDto
    | Query_prescription_get_prescription_SubstitutionRestrictionDto,
) -> Command_prescription_get_prescription_SubstitutionRestrictionDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(
        value, Command_prescription_get_prescription_SubstitutionRestrictionDto
    ):
        return value
    return Command_prescription_get_prescription_SubstitutionRestrictionDto(
        restriction_type=value.restriction_type,
        reason=value.reason,
        forbids_generic_substitution=value.forbids_generic_substitution,
    )


def to_http_prescription_get_prescription__public_expense_burden_dto(
    value: Command_prescription_get_prescription_PublicExpenseBurdenDto
    | Query_prescription_get_prescription_PublicExpenseBurdenDto,
) -> Command_prescription_get_prescription_PublicExpenseBurdenDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(value, Command_prescription_get_prescription_PublicExpenseBurdenDto):
        return value
    return Command_prescription_get_prescription_PublicExpenseBurdenDto(
        first=value.first, second=value.second, third=value.third, special=value.special
    )


def to_http_prescription_get_prescription__medicine_supplement_dto(
    value: Command_prescription_get_prescription_MedicineSupplementDto
    | Query_prescription_get_prescription_MedicineSupplementDto,
) -> Command_prescription_get_prescription_MedicineSupplementDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(value, Command_prescription_get_prescription_MedicineSupplementDto):
        return value
    return Command_prescription_get_prescription_MedicineSupplementDto(
        supplement_type=value.supplement_type, text=value.text, code=value.code
    )


def to_http_prescription_get_prescription__dosage_supplement_dto(
    value: Command_prescription_get_prescription_DosageSupplementDto
    | Query_prescription_get_prescription_DosageSupplementDto,
) -> Command_prescription_get_prescription_DosageSupplementDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(value, Command_prescription_get_prescription_DosageSupplementDto):
        return value
    return Command_prescription_get_prescription_DosageSupplementDto(
        supplement_type=value.supplement_type,
        text=value.text,
        code=value.code,
        site_code=value.site_code,
    )


def to_http_prescription_get_prescription__prescription_management_info_dto(
    value: Command_prescription_get_prescription_PrescriptionManagementInfoDto
    | Query_prescription_get_prescription_PrescriptionManagementInfoDto,
) -> Command_prescription_get_prescription_PrescriptionManagementInfoDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(
        value, Command_prescription_get_prescription_PrescriptionManagementInfoDto
    ):
        return value
    return Command_prescription_get_prescription_PrescriptionManagementInfoDto(
        refill_count=value.refill_count,
        split_total_count=value.split_total_count,
        split_iteration=value.split_iteration,
        residual_drug_instruction=value.residual_drug_instruction,
        narcotic_license_number=value.narcotic_license_number,
        patient_address=value.patient_address,
        patient_phone_number=value.patient_phone_number,
        notes=value.notes,
        clinical_info=value.clinical_info,
        lab_data=value.lab_data,
    )


def to_http_prescription_get_prescription__prescription_inquiry_dto(
    value: Command_prescription_get_prescription_PrescriptionInquiryDto
    | Query_prescription_get_prescription_PrescriptionInquiryDto,
) -> Command_prescription_get_prescription_PrescriptionInquiryDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(value, Command_prescription_get_prescription_PrescriptionInquiryDto):
        return value
    return Command_prescription_get_prescription_PrescriptionInquiryDto(
        inquiry_number=value.inquiry_number,
        pharmacist_id=value.pharmacist_id,
        inquired_at=value.inquired_at,
        category=value.category,
        content=value.content,
        response=to_http_prescription_get_prescription__prescriber_response_dto(
            value.response
        )
        if value.response is not None
        else None,
        is_open=value.is_open,
    )


def to_http_prescription_get_prescription__prescriber_response_dto(
    value: Command_prescription_get_prescription_PrescriberResponseDto
    | Query_prescription_get_prescription_PrescriberResponseDto,
) -> Command_prescription_get_prescription_PrescriberResponseDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(value, Command_prescription_get_prescription_PrescriberResponseDto):
        return value
    return Command_prescription_get_prescription_PrescriberResponseDto(
        responded_by=value.responded_by,
        responded_at=value.responded_at,
        result_type=value.result_type,
        content=value.content,
        blocks_dispensing=value.blocks_dispensing,
    )


def to_http_coverage_get_coverage_selection__coverage_selection_record_dto(
    value: Command_coverage_get_coverage_selection_CoverageSelectionRecordDto
    | Query_coverage_get_coverage_selection_CoverageSelectionRecordDto,
) -> Command_coverage_get_coverage_selection_CoverageSelectionRecordDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(
        value, Command_coverage_get_coverage_selection_CoverageSelectionRecordDto
    ):
        return value
    return Command_coverage_get_coverage_selection_CoverageSelectionRecordDto(
        id=value.id,
        corporate_id=value.corporate_id,
        store_id=value.store_id,
        patient_id=value.patient_id,
        applied_on=value.applied_on,
        selection=to_http_coverage_get_coverage_selection__coverage_selection_dto(
            value.selection
        ),
        recorded_at=value.recorded_at,
        recorded_by=value.recorded_by,
    )


def to_http_coverage_get_coverage_selection__coverage_selection_dto(
    value: Command_coverage_get_coverage_selection_CoverageSelectionDto
    | Query_coverage_get_coverage_selection_CoverageSelectionDto,
) -> Command_coverage_get_coverage_selection_CoverageSelectionDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(value, Command_coverage_get_coverage_selection_CoverageSelectionDto):
        return value
    return Command_coverage_get_coverage_selection_CoverageSelectionDto(
        insurance=to_http_coverage_get_coverage_selection__insurance_coverage_selection_dto(
            value.insurance
        )
        if value.insurance is not None
        else None,
        public_expenses=tuple(
            to_http_coverage_get_coverage_selection__public_expense_coverage_selection_dto(
                item
            )
            for item in value.public_expenses
        ),
    )


def to_http_coverage_get_coverage_selection__insurance_coverage_selection_dto(
    value: Command_coverage_get_coverage_selection_InsuranceCoverageSelectionDto
    | Query_coverage_get_coverage_selection_InsuranceCoverageSelectionDto,
) -> Command_coverage_get_coverage_selection_InsuranceCoverageSelectionDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(
        value, Command_coverage_get_coverage_selection_InsuranceCoverageSelectionDto
    ):
        return value
    return Command_coverage_get_coverage_selection_InsuranceCoverageSelectionDto(
        source_coverage_id=value.source_coverage_id,
        insurer_number=value.insurer_number,
        insured_symbol=value.insured_symbol,
        insured_number=value.insured_number,
        insured_type=value.insured_type,
        branch_number=value.branch_number,
        benefit_ratio=value.benefit_ratio,
    )


def to_http_coverage_get_coverage_selection__public_expense_coverage_selection_dto(
    value: Command_coverage_get_coverage_selection_PublicExpenseCoverageSelectionDto
    | Query_coverage_get_coverage_selection_PublicExpenseCoverageSelectionDto,
) -> Command_coverage_get_coverage_selection_PublicExpenseCoverageSelectionDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(
        value, Command_coverage_get_coverage_selection_PublicExpenseCoverageSelectionDto
    ):
        return value
    return Command_coverage_get_coverage_selection_PublicExpenseCoverageSelectionDto(
        source_coverage_id=value.source_coverage_id,
        priority=value.priority,
        payer_number=value.payer_number,
        recipient_number=value.recipient_number,
    )


def to_http_store_get_store__store_dto(
    value: Command_store_get_store_StoreDto | Query_store_get_store_StoreDto,
) -> Command_store_get_store_StoreDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(value, Command_store_get_store_StoreDto):
        return value
    return Command_store_get_store_StoreDto(
        id=value.id,
        corporate_id=value.corporate_id,
        name=value.name,
        name_kana=value.name_kana,
        name_romaji=value.name_romaji,
        postal_code=value.postal_code,
        address=value.address,
        phone_number=value.phone_number,
        fax_number=value.fax_number,
        email=value.email,
        code=value.code,
        insurance_pharmacy_number=value.insurance_pharmacy_number,
        status=value.status,
        status_history=tuple(
            to_http_store_get_store__store_status_change_dto(item)
            for item in value.status_history
        ),
        business_hours=to_http_store_business_hours__business_hours_dto(
            value.business_hours
        )
        if value.business_hours is not None
        else None,
    )


def to_http_store_get_store__store_status_change_dto(
    value: Command_store_get_store_StoreStatusChangeDto
    | Query_store_get_store_StoreStatusChangeDto,
) -> Command_store_get_store_StoreStatusChangeDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(value, Command_store_get_store_StoreStatusChangeDto):
        return value
    return Command_store_get_store_StoreStatusChangeDto(
        before=value.before,
        after=value.after,
        reason=value.reason,
        person_id=value.person_id,
        account_id=value.account_id,
        recorded_at=value.recorded_at,
    )


def to_http_store_business_hours__business_hours_dto(
    value: Command_store_business_hours_BusinessHoursDto
    | Query_store_business_hours_BusinessHoursDto,
) -> Command_store_business_hours_BusinessHoursDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(value, Command_store_business_hours_BusinessHoursDto):
        return value
    return Command_store_business_hours_BusinessHoursDto(
        weekly=tuple(
            to_http_store_business_hours__weekday_business_hours_dto(item)
            for item in value.weekly
        ),
        exceptions=tuple(
            to_http_store_business_hours__business_day_exception_dto(item)
            for item in value.exceptions
        ),
    )


def to_http_store_business_hours__weekday_business_hours_dto(
    value: Command_store_business_hours_WeekdayBusinessHoursDto
    | Query_store_business_hours_WeekdayBusinessHoursDto,
) -> Command_store_business_hours_WeekdayBusinessHoursDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(value, Command_store_business_hours_WeekdayBusinessHoursDto):
        return value
    return Command_store_business_hours_WeekdayBusinessHoursDto(
        weekday=value.weekday,
        slots=tuple(
            to_http_store_business_hours__business_hour_slot_dto(item)
            for item in value.slots
        ),
    )


def to_http_store_business_hours__business_hour_slot_dto(
    value: Command_store_business_hours_BusinessHourSlotDto
    | Query_store_business_hours_BusinessHourSlotDto,
) -> Command_store_business_hours_BusinessHourSlotDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(value, Command_store_business_hours_BusinessHourSlotDto):
        return value
    return Command_store_business_hours_BusinessHourSlotDto(
        opens_at=value.opens_at, closes_at=value.closes_at
    )


def to_http_store_business_hours__business_day_exception_dto(
    value: Command_store_business_hours_BusinessDayExceptionDto
    | Query_store_business_hours_BusinessDayExceptionDto,
) -> Command_store_business_hours_BusinessDayExceptionDto:
    """更新結果と参照結果を、既存のHTTP応答契約へ明示変換する。"""
    if isinstance(value, Command_store_business_hours_BusinessDayExceptionDto):
        return value
    return Command_store_business_hours_BusinessDayExceptionDto(
        on=value.on,
        slots=tuple(
            to_http_store_business_hours__business_hour_slot_dto(item)
            for item in value.slots
        ),
        note=value.note,
    )
