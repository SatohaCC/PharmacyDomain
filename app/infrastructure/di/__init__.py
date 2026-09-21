"""DI（依存性注入）とユースケース配線の公開窓口。"""

from app.infrastructure.di.bundles import (
    CorporateUseCases,
    CoverageUseCases,
    DispensingUseCases,
    IntegrationUseCases,
    MedicationHistoryUseCases,
    MedicineCatalogUseCases,
    PatientUseCases,
    PrescriptionUseCases,
    ReceptionUseCases,
    StaffUseCases,
    StoreUseCases,
)
from app.infrastructure.di.bundles.identity import IdentityUseCases
from app.infrastructure.di.registry import PostgresUseCaseRegistry
from app.infrastructure.di.root import PostgresCompositionRoot, PostgresRequestScope

__all__ = [
    "CorporateUseCases",
    "CoverageUseCases",
    "DispensingUseCases",
    "IdentityUseCases",
    "IntegrationUseCases",
    "MedicationHistoryUseCases",
    "MedicineCatalogUseCases",
    "PatientUseCases",
    "PostgresCompositionRoot",
    "PostgresRequestScope",
    "PostgresUseCaseRegistry",
    "PrescriptionUseCases",
    "ReceptionUseCases",
    "StaffUseCases",
    "StoreUseCases",
]
