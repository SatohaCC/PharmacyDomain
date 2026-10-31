"""外部連携（Integration）のユースケース束。"""

from __future__ import annotations

from app.application.common.clock import Clock
from app.application.composition.registry import (
    IntegrationUseCases,
    PatientUseCases,
)
from app.application.corporate.commands.services.corporate_access import (
    CorporateAccessService,
)
from app.application.integration.commands.ingest_nsips import IngestNsipsUseCase
from app.application.integration.queries.get_nsips_source import GetNsipsSourceUseCase
from app.infrastructure.di.repositories import (
    PostgresRepositorySet,
)
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.infrastructure.readers.integration_nsips_source import (
    PostgresGetNsipsSourceQueryReader,
)


def build_integration_use_cases(
    repositories: PostgresRepositorySet,
    corporate_access: CorporateAccessService,
    patient_use_cases: PatientUseCases,
    unit_of_work: PostgresUnitOfWork,
    clock: Clock,
) -> IntegrationUseCases:
    """外部連携ユースケース束を組み立てる。"""
    ingest_nsips = IngestNsipsUseCase(
        corporate_access=corporate_access,
        unit_of_work=unit_of_work,
        patient_external_id_repo=repositories.patient_external_identifier,
        patient_repo=repositories.patient,
        reception_repo=repositories.reception,
        store_repo=repositories.store,
        register_patient_use_case=patient_use_cases.register,
        register_patient_external_id_use_case=patient_use_cases.register_external_identifier,
        medication_history_repo=repositories.medication_history,
        clock=clock,
    )
    reader = PostgresGetNsipsSourceQueryReader(
        reception_repository=repositories.reception,
        medication_history_repository=repositories.medication_history,
    )
    get_nsips_source = GetNsipsSourceUseCase(
        reader=reader,
        corporate_access=corporate_access,
    )
    return IntegrationUseCases(
        ingest_nsips=ingest_nsips,
        get_nsips_source=get_nsips_source,
    )
