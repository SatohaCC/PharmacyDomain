"""Applicationのcorporate_activity_guardを定義する。"""

from __future__ import annotations

from app.application.common.organization_lock import OrganizationLock
from app.application.corporate.commands.services.support import (
    load_active_corporate_or_raise,
)
from app.domain.care_event.entities import Event, EventDefinition
from app.domain.corporate.repositories import CorporateRepository
from app.domain.coverage.entities import CoverageSelectionRecord, PatientCoverage
from app.domain.dispensing.entities import DispensingProcess
from app.domain.medication_history.entities import (
    MedicationHistoryCategoryCatalog,
    MedicationHistoryRecord,
    PatientMedicalProfile,
)
from app.domain.patient.entities import Patient, PatientExternalIdentifier
from app.domain.prescription.entities import Prescription
from app.domain.reception.entities import Reception
from app.domain.staff.entities import Staff
from app.domain.store.entities import Store, StoreManagerAssignment


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
