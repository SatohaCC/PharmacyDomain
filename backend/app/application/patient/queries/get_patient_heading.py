"""Applicationのget_patient_headingを定義する。"""

from __future__ import annotations

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.patient.interfaces.get_patient_heading_query_reader import (
    GetPatientHeadingQueryReader,
)
from app.application.patient.queries.dtos.get_patient_heading import PatientHeadingDto
from app.application.patient.queries.models import GetPatientHeadingQuery
from app.domain.corporate.identifiers import CorporateId


class GetPatientHeadingUseCase:
    def __init__(
        self,
        reader: GetPatientHeadingQueryReader,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._reader = reader
        self._corporate_access = corporate_access

    async def execute(self, query: GetPatientHeadingQuery) -> PatientHeadingDto:
        """認可と法人境界を確かめて頭書きを取得する。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.VIEW_PATIENT_HEADING
        )
        return await self._reader.read(query)
