"""Applicationのlist_patientsを定義する。"""

from __future__ import annotations

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.patient.interfaces.list_patients_query_reader import (
    ListPatientsQueryReader,
)
from app.application.patient.queries.dtos.list_patients import PatientSummaryDto
from app.application.patient.queries.models import ListPatientsQuery
from app.domain.corporate.identifiers import CorporateId


class ListPatientsUseCase:
    """患者一覧を取得するユースケース。"""

    def __init__(
        self,
        reader: ListPatientsQueryReader,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._reader = reader
        self._corporate_access = corporate_access

    async def execute(self, query: ListPatientsQuery) -> list[PatientSummaryDto]:
        corporate_id = CorporateId.parse(query.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.VIEW_PATIENT
        )
        return await self._reader.read(query)
