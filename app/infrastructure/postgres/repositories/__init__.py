"""PostgreSQL Repository 実装。

**1集約1ファイル**とする。集約は互いに独立して変わる（処方箋の検索列を足しても
調剤・薬歴・頭書きは変わらない）ので、束ねてもファイル内で区切り線を引き直す
ことになり、境界を探す手間だけが残る。ここに並ぶファイル名は Repository 名
（``Postgres`` と ``Repository`` を除いたもの）と一致するので、集約から実装へ
一意にたどれる。

ユースケースの配線側（``app/infrastructure/postgres`` 直下）は逆に束のままに
する。あちらは ``CorporateAccessService`` / ``Clock`` / ``UnitOfWork`` という
同じ依存を配り回しており、渡すものが増えると束の中の複数のユースケースが同時に
変わるため、変更の単位が束と一致する。
"""

from dataclasses import dataclass
from typing import Self

from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.infrastructure.postgres.repositories.corporate import (
    PostgresCorporateRepository,
)
from app.infrastructure.postgres.repositories.coverage_selection_record import (
    PostgresCoverageSelectionRecordRepository,
)
from app.infrastructure.postgres.repositories.dispensing_process import (
    PostgresDispensingProcessRepository,
)
from app.infrastructure.postgres.repositories.medication_history import (
    PostgresMedicationHistoryRepository,
)
from app.infrastructure.postgres.repositories.medicine_catalog import (
    PostgresMedicineCatalogRepository,
)
from app.infrastructure.postgres.repositories.patient import PostgresPatientRepository
from app.infrastructure.postgres.repositories.patient_coverage import (
    PostgresPatientCoverageRepository,
)
from app.infrastructure.postgres.repositories.patient_external_identifier import (
    PostgresPatientExternalIdentifierRepository,
)
from app.infrastructure.postgres.repositories.patient_medical_profile import (
    PostgresPatientMedicalProfileRepository,
)
from app.infrastructure.postgres.repositories.prescription import (
    PostgresPrescriptionRepository,
)
from app.infrastructure.postgres.repositories.staff import PostgresStaffRepository
from app.infrastructure.postgres.repositories.store import PostgresStoreRepository


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


__all__ = [
    "PostgresCorporateRepository",
    "PostgresCoverageSelectionRecordRepository",
    "PostgresDispensingProcessRepository",
    "PostgresMedicationHistoryRepository",
    "PostgresMedicineCatalogRepository",
    "PostgresPatientCoverageRepository",
    "PostgresPatientExternalIdentifierRepository",
    "PostgresPatientMedicalProfileRepository",
    "PostgresPatientRepository",
    "PostgresPrescriptionRepository",
    "PostgresRepositorySet",
    "PostgresStaffRepository",
    "PostgresStoreRepository",
]
