"""外部連携（Integration）のユースケース束。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.common.clock import Clock
from app.application.corporate.corporate_access import CorporateAccessService
from app.application.integration.nsips.ingest_nsips import IngestNsipsUseCase
from app.infrastructure.di.bundles.clinical import (
    DispensingUseCases,
    MedicationHistoryUseCases,
    PrescriptionUseCases,
)
from app.infrastructure.di.bundles.patient_care import (
    CoverageUseCases,
    PatientUseCases,
    ReceptionUseCases,
)
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.infrastructure.postgres.repositories import PostgresRepositorySet


@dataclass(frozen=True, slots=True)
class IntegrationUseCases:
    """外部連携コンテキストのユースケース一覧。"""

    ingest_nsips: IngestNsipsUseCase


def build_integration_use_cases(
    repositories: PostgresRepositorySet,
    corporate_access: CorporateAccessService,
    patient_use_cases: PatientUseCases,
    coverage_use_cases: CoverageUseCases,
    reception_use_cases: ReceptionUseCases,
    prescription_use_cases: PrescriptionUseCases,
    dispensing_use_cases: DispensingUseCases,
    medication_history_use_cases: MedicationHistoryUseCases,
    unit_of_work: PostgresUnitOfWork,
    clock: Clock,
) -> IntegrationUseCases:
    """外部連携ユースケース束を組み立てる。"""
    ingest_nsips = IngestNsipsUseCase(
        corporate_access=corporate_access,
        unit_of_work=unit_of_work,
        patient_external_id_repo=repositories.patient_external_identifier,
        patient_repo=repositories.patient,
        prescription_repo=repositories.prescription,
        dispensing_repo=repositories.dispensing,
        patient_coverage_repo=repositories.patient_coverage,
        register_coverage_use_case=coverage_use_cases.register,
        record_coverage_selection_use_case=reception_use_cases.record_coverage_selection,
        register_patient_use_case=patient_use_cases.register,
        register_patient_external_id_use_case=patient_use_cases.register_external_identifier,
        register_prescription_use_case=prescription_use_cases.register,
        ready_for_dispensing_use_case=prescription_use_cases.ready_for_dispensing,
        start_dispensing_use_case=dispensing_use_cases.start,
        start_medication_history_use_case=medication_history_use_cases.start,
        add_follow_up_use_case=medication_history_use_cases.add_follow_up,
        list_medication_histories_use_case=medication_history_use_cases.list_by_patient,
        clock=clock,
    )
    return IntegrationUseCases(ingest_nsips=ingest_nsips)
