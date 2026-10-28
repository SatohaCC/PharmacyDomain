"""Applicationのget_medication_historyを定義する。"""

from __future__ import annotations

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.medication_history.interfaces.get_medication_history_query_reader import (
    GetMedicationHistoryQueryReader,
)
from app.application.medication_history.queries.dtos.get_medication_history import (
    MedicationHistoryDto,
)
from app.application.medication_history.queries.models import GetMedicationHistoryQuery
from app.domain.corporate.identifiers import CorporateId


class GetMedicationHistoryUseCase:
    def __init__(
        self,
        reader: GetMedicationHistoryQueryReader,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._reader = reader
        self._corporate_access = corporate_access

    async def execute(self, query: GetMedicationHistoryQuery) -> MedicationHistoryDto:
        """指定法人の薬歴をDTOで返す。エンティティは返さない。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.VIEW_MEDICATION_HISTORY
        )
        return await self._reader.read(query)
