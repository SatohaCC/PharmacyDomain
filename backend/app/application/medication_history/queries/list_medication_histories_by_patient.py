"""Applicationのlist_medication_histories_by_patientを定義する。"""

from __future__ import annotations

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.medication_history.interfaces.list_medication_histories_by_patient_query_reader import (
    ListMedicationHistoriesByPatientQueryReader,
)
from app.application.medication_history.queries.dtos.get_medication_history import (
    MedicationHistoryDto,
)
from app.application.medication_history.queries.models import (
    ListMedicationHistoriesQuery,
)
from app.domain.corporate.identifiers import CorporateId


class ListMedicationHistoriesByPatientUseCase:
    def __init__(
        self,
        reader: ListMedicationHistoriesByPatientQueryReader,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._reader = reader
        self._corporate_access = corporate_access

    async def execute(
        self, query: ListMedicationHistoriesQuery
    ) -> tuple[MedicationHistoryDto, ...]:
        """指定法人・患者の薬歴をDTOで返す。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.VIEW_MEDICATION_HISTORY
        )
        return await self._reader.read(query)
