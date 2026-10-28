"""Applicationのget_patient_coverageを定義する。"""

from __future__ import annotations

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.coverage.interfaces.get_patient_coverage_query_reader import (
    GetPatientCoverageQueryReader,
)
from app.application.coverage.queries.dtos.get_patient_coverage import (
    PatientCoverageDto,
)
from app.application.coverage.queries.models import GetPatientCoverageQuery
from app.domain.corporate.identifiers import CorporateId
from app.domain.coverage.identifiers import PatientCoverageId


class GetPatientCoverageUseCase:
    def __init__(
        self,
        reader: GetPatientCoverageQueryReader,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._reader = reader
        self._corporate_access = corporate_access

    async def execute(self, query: GetPatientCoverageQuery) -> PatientCoverageDto:
        """法人境界を確認して患者資格DTOを返す。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.VIEW_COVERAGE
        )
        PatientCoverageId.parse(query.coverage_id)
        return await self._reader.read(query)
