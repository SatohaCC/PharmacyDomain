"""PostgreSQL 経路の Composition Root 公開窓口。"""

from app.infrastructure.composition.corporate import CorporateUseCases
from app.infrastructure.composition.coverage import CoverageUseCases
from app.infrastructure.composition.dispensing import DispensingUseCases
from app.infrastructure.composition.medication_history import MedicationHistoryUseCases
from app.infrastructure.composition.medicine_catalog import MedicineCatalogUseCases
from app.infrastructure.composition.patient import PatientUseCases
from app.infrastructure.composition.prescription import PrescriptionUseCases
from app.infrastructure.composition.reception import ReceptionUseCases
from app.infrastructure.composition.repositories import PostgresRepositorySet
from app.infrastructure.composition.root import PostgresCompositionRoot
from app.infrastructure.composition.scope import (
    PostgresRequestScope,
    PostgresUseCaseRegistry,
)
from app.infrastructure.composition.staff import StaffUseCases
from app.infrastructure.composition.store import StoreUseCases

__all__ = [
    "CorporateUseCases",
    "CoverageUseCases",
    "DispensingUseCases",
    "MedicationHistoryUseCases",
    "MedicineCatalogUseCases",
    "PatientUseCases",
    "PostgresCompositionRoot",
    "PostgresRepositorySet",
    "PostgresRequestScope",
    "PostgresUseCaseRegistry",
    "PrescriptionUseCases",
    "ReceptionUseCases",
    "StaffUseCases",
    "StoreUseCases",
]
