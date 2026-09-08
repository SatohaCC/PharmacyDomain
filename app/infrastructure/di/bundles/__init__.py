"""コンテキストごとのユースケース束パッケージ。"""

from app.infrastructure.di.bundles.clinical import (
    DispensingUseCases,
    MedicationHistoryUseCases,
    PrescriptionUseCases,
    build_dispensing_use_cases,
    build_medication_history_use_cases,
    build_prescription_use_cases,
)
from app.infrastructure.di.bundles.medicine_catalog import (
    MedicineCatalogUseCases,
    build_medicine_catalog_use_cases,
)
from app.infrastructure.di.bundles.organization import (
    CorporateUseCases,
    StaffUseCases,
    StoreUseCases,
    build_corporate_use_cases,
    build_staff_use_cases,
    build_store_use_cases,
)
from app.infrastructure.di.bundles.patient_care import (
    CoverageUseCases,
    PatientUseCases,
    ReceptionUseCases,
    build_coverage_use_cases,
    build_patient_use_cases,
    build_reception_use_cases,
)

__all__ = [
    "CorporateUseCases",
    "CoverageUseCases",
    "DispensingUseCases",
    "MedicationHistoryUseCases",
    "MedicineCatalogUseCases",
    "PatientUseCases",
    "PrescriptionUseCases",
    "ReceptionUseCases",
    "StaffUseCases",
    "StoreUseCases",
    "build_corporate_use_cases",
    "build_coverage_use_cases",
    "build_dispensing_use_cases",
    "build_medication_history_use_cases",
    "build_medicine_catalog_use_cases",
    "build_patient_use_cases",
    "build_prescription_use_cases",
    "build_reception_use_cases",
    "build_staff_use_cases",
    "build_store_use_cases",
]
