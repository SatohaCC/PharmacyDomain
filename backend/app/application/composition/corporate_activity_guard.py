"""通常業務の保存と法人の利用停止を直列化する境界。"""

from app.application.common.organization_lock import OrganizationLock
from app.application.corporate.support import load_active_corporate_or_raise
from app.domain.care_event.event import Event
from app.domain.care_event.event_definition import EventDefinition
from app.domain.corporate.repository import CorporateRepository
from app.domain.coverage.coverage_selection_record import CoverageSelectionRecord
from app.domain.coverage.patient_coverage import PatientCoverage
from app.domain.dispensing.dispensing_process import DispensingProcess
from app.domain.medication_history.category_catalog import (
    MedicationHistoryCategoryCatalog,
)
from app.domain.medication_history.medication_history_record import (
    MedicationHistoryRecord,
)
from app.domain.medication_history.patient_medical_profile import PatientMedicalProfile
from app.domain.patient.external_identifier import PatientExternalIdentifier
from app.domain.patient.patient import Patient
from app.domain.prescription.prescription import Prescription
from app.domain.reception.reception import Reception
from app.domain.staff.staff import Staff
from app.domain.store.manager_assignment import StoreManagerAssignment
from app.domain.store.store import Store


class CorporateActivityWriteGuard:
    """通常業務の集約は、保存直前にも法人の有効状態を確認する。"""

    def __init__(self, repository: CorporateRepository, lock: OrganizationLock) -> None:
        self._repository = repository
        self._lock = lock

    async def check(self, aggregate: object, is_new: bool) -> None:
        """法人状態の確認からコミットまで、利用停止との競合を防ぐ。

        法人自体の状態変更、全法人共通のマスタ、本人・アカウント管理は
        通常業務の保存ではないため、この境界の対象にしない。
        """
        if not isinstance(
            aggregate,
            (
                Store,
                Staff,
                StoreManagerAssignment,
                Patient,
                PatientExternalIdentifier,
                PatientCoverage,
                CoverageSelectionRecord,
                Reception,
                Prescription,
                DispensingProcess,
                Event,
                EventDefinition,
                MedicationHistoryRecord,
                PatientMedicalProfile,
                MedicationHistoryCategoryCatalog,
            ),
        ):
            return
        corporate_id = aggregate.corporate_id
        if corporate_id is None:
            return
        await self._lock.acquire(f"corporate:{corporate_id.value}")
        await load_active_corporate_or_raise(self._repository, corporate_id)
