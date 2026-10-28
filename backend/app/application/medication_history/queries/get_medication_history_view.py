"""Applicationのget_medication_history_viewを定義する。"""

from __future__ import annotations

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.medication_history.interfaces.get_medication_history_view_query_reader import (
    GetMedicationHistoryViewQueryReader,
)
from app.application.medication_history.queries.dtos.get_medication_history_view import (
    MedicationHistoryViewDto,
)
from app.application.medication_history.queries.models import (
    GetMedicationHistoryViewQuery,
)
from app.domain.corporate.identifiers import CorporateId


class GetMedicationHistoryViewUseCase:
    def __init__(
        self,
        reader: GetMedicationHistoryViewQueryReader,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._reader = reader
        self._corporate_access = corporate_access

    async def execute(
        self, query: GetMedicationHistoryViewQuery
    ) -> MedicationHistoryViewDto:
        """薬歴本文と患者現行情報を認可後に返す。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.VIEW_MEDICATION_HISTORY
        )
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.VIEW_PATIENT
        )
        return await self._reader.read(query)
