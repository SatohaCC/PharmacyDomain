"""1スコープ分の PostgreSQL Repository 一式。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Self

from app.infrastructure.postgres.repositories.corporate import (
    PostgresCorporateRepository,
)
from app.infrastructure.postgres.repositories.coverage import (
    PostgresPatientCoverageRepository,
)
from app.infrastructure.postgres.repositories.dispensing import (
    PostgresDispensingProcessRepository,
)
from app.infrastructure.postgres.repositories.medication_history import (
    PostgresMedicationHistoryRepository,
    PostgresPatientMedicalProfileRepository,
)
from app.infrastructure.postgres.repositories.medicine_catalog import (
    PostgresMedicineCatalogRepository,
)
from app.infrastructure.postgres.repositories.patient import (
    PostgresPatientExternalIdentifierRepository,
    PostgresPatientRepository,
)
from app.infrastructure.postgres.repositories.prescription import (
    PostgresPrescriptionRepository,
)
from app.infrastructure.postgres.repositories.reception import (
    PostgresCoverageSelectionRecordRepository,
)
from app.infrastructure.postgres.repositories.staff import PostgresStaffRepository
from app.infrastructure.postgres.repositories.store import PostgresStoreRepository
from app.infrastructure.postgres.unit_of_work import PostgresUnitOfWork


@dataclass(frozen=True, slots=True)
class PostgresRepositorySet:
    """同じ Unit of Work を共有する Repository の集合。

    全Repositoryが**同一のUoWインスタンス**を持つことが要点である。読み込んだ
    行の世代はUoWが持つので、別々のUoWから作ると同じ行の世代が分裂し、
    楽観ロックが当たらなくなる。
    """

    corporate: PostgresCorporateRepository
    store: PostgresStoreRepository
    staff: PostgresStaffRepository
    patient: PostgresPatientRepository
    patient_external_identifier: PostgresPatientExternalIdentifierRepository
    patient_coverage: PostgresPatientCoverageRepository
    coverage_selection_record: PostgresCoverageSelectionRecordRepository
    prescription: PostgresPrescriptionRepository
    dispensing: PostgresDispensingProcessRepository
    medication_history: PostgresMedicationHistoryRepository
    patient_medical_profile: PostgresPatientMedicalProfileRepository
    medicine_catalog: PostgresMedicineCatalogRepository

    @classmethod
    def create(cls, unit_of_work: PostgresUnitOfWork) -> Self:
        """1つの Unit of Work から全Repositoryを組み立てる。"""
        return cls(
            corporate=PostgresCorporateRepository(unit_of_work),
            store=PostgresStoreRepository(unit_of_work),
            staff=PostgresStaffRepository(unit_of_work),
            patient=PostgresPatientRepository(unit_of_work),
            patient_external_identifier=PostgresPatientExternalIdentifierRepository(
                unit_of_work
            ),
            patient_coverage=PostgresPatientCoverageRepository(unit_of_work),
            coverage_selection_record=PostgresCoverageSelectionRecordRepository(
                unit_of_work
            ),
            prescription=PostgresPrescriptionRepository(unit_of_work),
            dispensing=PostgresDispensingProcessRepository(unit_of_work),
            medication_history=PostgresMedicationHistoryRepository(unit_of_work),
            patient_medical_profile=PostgresPatientMedicalProfileRepository(
                unit_of_work
            ),
            medicine_catalog=PostgresMedicineCatalogRepository(unit_of_work),
        )
