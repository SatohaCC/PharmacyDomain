"""Event起票時の患者参照Boundary Fake。"""

from app.application.access_control.exceptions import TenantBoundaryNotFoundError
from app.application.care_event.references import EventPatientBoundary
from app.domain.corporate.identifiers import CorporateId
from app.domain.patient.identifiers import PatientId


class FakeEventPatientBoundary(EventPatientBoundary):
    """登録済みの法人・患者組だけを許可する。"""

    def __init__(self) -> None:
        self.patients: set[tuple[CorporateId, PatientId]] = set()

    def register(self, *, corporate_id: CorporateId, patient_id: PatientId) -> None:
        self.patients.add((corporate_id, patient_id))

    async def require_exists(
        self, *, corporate_id: CorporateId, patient_id: PatientId
    ) -> None:
        if (corporate_id, patient_id) not in self.patients:
            raise TenantBoundaryNotFoundError()
