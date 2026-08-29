"""コンテキスト間Boundaryを接続するComposition公開窓口。"""

from app.application.composition.coverage_references import (
    CoveragePatientReferenceAdapter,
)
from app.application.composition.coverage_selection_adapter import (
    CoverageSelectionAdapter,
)
from app.application.composition.dispensing_references import (
    DispensingStaffQualificationAdapter,
    DispensingStoreReferenceAdapter,
    PrescriptionSourceAdapter,
)
from app.application.composition.medication_history_references import (
    CounselorQualificationAdapter,
    DispensingSourceAdapter,
    MedicationHistoryStoreReferenceAdapter,
)
from app.application.composition.medicine_restriction_adapter import (
    MedicineCatalogRestrictionAdapter,
)
from app.application.composition.prescription_references import (
    CoverageSelectionPublicExpenseAdapter,
    PrescriptionPatientReferenceAdapter,
    PrescriptionStaffQualificationAdapter,
    PrescriptionStoreReferenceAdapter,
)
from app.application.composition.reception_references import (
    ReceptionPatientReferenceAdapter,
    ReceptionStoreReferenceAdapter,
)
from app.application.composition.system_clock import SystemUtcClock

__all__ = [
    "CounselorQualificationAdapter",
    "CoveragePatientReferenceAdapter",
    "CoverageSelectionAdapter",
    "CoverageSelectionPublicExpenseAdapter",
    "DispensingSourceAdapter",
    "DispensingStaffQualificationAdapter",
    "DispensingStoreReferenceAdapter",
    "MedicationHistoryStoreReferenceAdapter",
    "MedicineCatalogRestrictionAdapter",
    "PrescriptionPatientReferenceAdapter",
    "PrescriptionSourceAdapter",
    "PrescriptionStaffQualificationAdapter",
    "PrescriptionStoreReferenceAdapter",
    "ReceptionPatientReferenceAdapter",
    "ReceptionStoreReferenceAdapter",
    "SystemUtcClock",
]
