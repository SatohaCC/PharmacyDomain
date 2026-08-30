"""患者コンテキストのユースケース束。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.corporate.corporate_access import CorporateAccessService
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
from app.infrastructure.composition.repositories import PostgresRepositorySet


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
